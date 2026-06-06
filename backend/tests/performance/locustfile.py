"""
Testy wydajnościowe TrendEconomy API — Locust.
Symuluje typowe zachowanie użytkownika dashboardu.

Uruchomienie z UI (http://localhost:8089):
    locust -f tests/performance/locustfile.py --host http://localhost:8000

Headless (CI):
    locust -f tests/performance/locustfile.py --headless \
        --host http://localhost:8000 --users 20 --spawn-rate 5 \
        --run-time 60s --html locust_report.html
"""

import random
from locust import HttpUser, task, between, events
import structlog

logger = structlog.get_logger()

EU_COUNTRY_CODES = [
    "PL", "DE", "FR", "IT", "ES", "NL", "BE", "SE",
    "AT", "RO", "CZ", "HU", "PT", "GR", "FI", "DK",
]

# Rzeczywiste kody z app/ingestion/indicators_config.py
INDICATOR_CODES = [
    "gdp_per_capita_eur",
    "gdp_per_capita_usd",
    "unemployment_rate_eu",
    "unemployment_rate_wb",
    "population_total_eu",
    "life_expectancy",
    "inflation_cpi",
]

YEAR_RANGES = [
    (2000, 2023),
    (2010, 2023),
    (2015, 2023),
    (2005, 2015),
]


def random_countries(n: int = 3) -> str:
    return ",".join(random.sample(EU_COUNTRY_CODES, min(n, len(EU_COUNTRY_CODES))))


class DashboardUser(HttpUser):
    """Zwykły user dashboardu — pauza 1-3s między requestami."""
    wait_time = between(1, 3)

    @task(1)
    def health_check(self):
        with self.client.get("/api/v1/health", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health check failed: {resp.status_code}")

    @task(3)
    def list_countries(self):
        with self.client.get("/api/v1/countries/", catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if not isinstance(data, list) or len(data) == 0:
                    resp.failure("Expected non-empty list of countries")
                else:
                    resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def list_indicators(self):
        with self.client.get("/api/v1/indicators/", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(5)
    def get_indicator_data_default(self):
        """Typowe zapytanie o dane — serce dashboardu."""
        indicator = random.choice(INDICATOR_CODES)
        countries = random_countries(3)
        year_from, year_to = random.choice(YEAR_RANGES)

        with self.client.get(
            f"/api/v1/data/{indicator}",
            params={
                "countries": countries,
                "year_from": year_from,
                "year_to": year_to,
            },
            name="/api/v1/data/[indicator]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(4)
    def get_indicator_data_wide_range(self):
        """Długi zakres lat — test wydajności przy większym zbiorze."""
        indicator = random.choice(INDICATOR_CODES)
        countries = random_countries(5)

        with self.client.get(
            f"/api/v1/data/{indicator}",
            params={"countries": countries, "year_from": 2000, "year_to": 2023},
            name="/api/v1/data/[indicator]?wide_range",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def get_single_country(self):
        code = random.choice(EU_COUNTRY_CODES)
        with self.client.get(
            f"/api/v1/countries/{code}",
            name="/api/v1/countries/[code]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 404:
                resp.failure(f"Country {code} not found — check seed data")
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(1)
    def get_nonexistent_indicator(self):
        """Test obsługi błędów — serwer powinien zwrócić 404, nie 500."""
        with self.client.get(
            "/api/v1/data/nonexistent_indicator_xyz",
            name="/api/v1/data/[invalid]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 404:
                resp.success()
            else:
                resp.failure(f"Expected 404 for invalid indicator, got {resp.status_code}")


class AnalystUser(HttpUser):
    """Heavy user — analityk pobierający duże zbiory danych."""
    wait_time = between(0.5, 1.5)
    weight = 1

    @task(8)
    def heavy_data_query(self):
        indicator = random.choice(INDICATOR_CODES)
        countries = random_countries(8)

        with self.client.get(
            f"/api/v1/data/{indicator}",
            params={"countries": countries, "year_from": 1995, "year_to": 2023},
            name="/api/v1/data/[indicator]?heavy",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def list_all(self):
        self.client.get("/api/v1/countries/")
        self.client.get("/api/v1/indicators/")


@events.quitting.add_listener
def on_locust_quit(environment, **kwargs):
    stats = environment.stats.total
    logger.info(
        "locust_test_finished",
        total_requests=stats.num_requests,
        failures=stats.num_failures,
        failure_rate=round(stats.fail_ratio * 100, 2),
        avg_response_ms=round(stats.avg_response_time, 2),
        p95_response_ms=stats.get_response_time_percentile(0.95),
        p99_response_ms=stats.get_response_time_percentile(0.99),
        rps=round(stats.current_rps, 2),
    )
    if stats.fail_ratio > 0.05:
        logger.error("locust_failure_threshold_exceeded", failure_rate_pct=round(stats.fail_ratio * 100, 2))
        environment.process_exit_code = 1
