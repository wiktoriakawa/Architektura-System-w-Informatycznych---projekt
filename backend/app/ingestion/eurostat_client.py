"""
Klient Eurostat REST API (SDMX 2.1, JSON-stat 2.0).

Dokumentacja źródłowa:
  https://wikis.ec.europa.eu/display/EUROSTATHELP/API+-+Getting+started

Endpoint bazowy:
  https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/<DATASET>?format=JSON&...

Odpowiedź jest w formacie JSON-stat 2.0 — sparsowana lista wartości indeksowana
zlinearizowanym numerem komórki w wielowymiarowej kostce (geo × time × ...).
Naszą rolą jest:
  1. zbudowanie zapytania z filtrami (geo, time, jednostka, kategoria),
  2. odczytanie pozycji wymiarów `geo` i `time` z odpowiedzi,
  3. rozplecenie wartości do listy krotek (kraj_iso2, rok, wartość).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

import httpx
import structlog

from app.ingestion.indicators_config import IndicatorConfig

logger = structlog.get_logger()

EUROSTAT_BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"
DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 2.0


@dataclass(frozen=True)
class EurostatObservation:
    """Pojedyncza obserwacja po sparsowaniu odpowiedzi JSON-stat."""

    country_iso2: str
    year: int
    value: float


class EurostatClient:
    """Lekki, synchroniczny klient Eurostat API oparty na httpx."""

    def __init__(
        self,
        base_url: str = EUROSTAT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Klient HTTP można wstrzyknąć z zewnątrz (ułatwia testowanie).
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    # ------------------------------------------------------------------ API

    def fetch(
        self,
        indicator: IndicatorConfig,
        countries_iso2: Iterable[str],
        year_from: int,
        year_to: int,
    ) -> list[EurostatObservation]:
        """Pobiera obserwacje dla wskaźnika, listy krajów i zakresu lat."""
        if indicator.source != "eurostat":
            raise ValueError(f"Indicator {indicator.code} is not an Eurostat indicator")

        url = f"{self.base_url}/{indicator.dataset}"
        params: list[tuple[str, str]] = [("format", "JSON"), ("lang", "EN")]

        # Filtry SDMX (jednostka, kategoria, płeć itp.)
        for key, value in indicator.filters.items():
            params.append((key, value))

        # Wymiar geograficzny — kody ISO2 (Eurostat używa "EL" zamiast "GR" dla Grecji,
        # "UK" zamiast "GB" dla Wlk. Brytanii — ale dla państw UE 27 nie kolidują).
        for country in countries_iso2:
            params.append(("geo", country))

        # Zakres lat
        params.append(("sinceTimePeriod", str(year_from)))
        params.append(("untilTimePeriod", str(year_to)))

        logger.info(
            "eurostat_request",
            dataset=indicator.dataset,
            indicator=indicator.code,
            year_from=year_from,
            year_to=year_to,
            countries=list(countries_iso2),
        )

        payload = self._get_with_retry(url, params, indicator.code)

        observations = self._parse_jsonstat(payload)
        logger.info(
            "eurostat_response_parsed",
            dataset=indicator.dataset,
            observations=len(observations),
        )
        return observations

    def _get_with_retry(self, url: str, params, indicator_code: str) -> dict:
        """Pobiera URL z retry na błędach sieciowych (timeout, network unreachable, 5xx)."""
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                # Nie powtarzamy błędów 4xx (poza 429) — to nasza wina, nie sieć.
                if isinstance(exc, httpx.HTTPStatusError):
                    status = exc.response.status_code
                    if status < 500 and status != 429:
                        raise
                last_error = exc
                logger.warning(
                    "eurostat_request_retry",
                    indicator=indicator_code,
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SEC * attempt)
        # Wszystkie próby padły — propagujemy ostatni błąd.
        assert last_error is not None
        raise last_error

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "EurostatClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------ JSON-stat parser

    @staticmethod
    def _parse_jsonstat(payload: dict) -> list[EurostatObservation]:
        """
        Rozplata sparsowaną kostkę JSON-stat 2.0 do listy obserwacji.

        Indeks `value` to liczba całkowita = zlinearizowana pozycja w kostce
        wielowymiarowej. Krok (stride) dla wymiaru i = iloczyn rozmiarów
        wymiarów i+1..n-1. Wymiary geograficzny i czasowy odczytujemy z
        `dimension.geo.category.index` oraz `dimension.time.category.index`.
        """
        dimensions: list[str] = payload.get("id", [])
        sizes: list[int] = payload.get("size", [])
        if not dimensions or not sizes or len(dimensions) != len(sizes):
            raise ValueError("Malformed JSON-stat response: missing or inconsistent id/size")

        try:
            geo_axis = dimensions.index("geo")
            time_axis = dimensions.index("time")
        except ValueError as e:
            raise ValueError("JSON-stat response missing 'geo' or 'time' dimension") from e

        dim_data = payload.get("dimension", {})
        # Odwracamy mapy {kod -> indeks} na {indeks -> kod} dla wymiarów geo i time.
        geo_index = dim_data["geo"]["category"]["index"]
        time_index = dim_data["time"]["category"]["index"]
        geo_by_pos: dict[int, str] = {pos: code for code, pos in geo_index.items()}
        time_by_pos: dict[int, str] = {pos: code for code, pos in time_index.items()}

        # Strides — iloczyn rozmiarów wymiarów na prawo od danego wymiaru.
        strides: list[int] = [1] * len(sizes)
        for i in range(len(sizes) - 2, -1, -1):
            strides[i] = strides[i + 1] * sizes[i + 1]

        values = payload.get("value", {})
        observations: list[EurostatObservation] = []

        for raw_index, raw_value in values.items():
            if raw_value is None:
                continue
            # Klucz może być stringiem (sparse dict) lub intem (przy gęstym formacie).
            idx = int(raw_index)
            # Wyciągamy pozycję dla wymiaru geo i time.
            geo_pos = (idx // strides[geo_axis]) % sizes[geo_axis]
            time_pos = (idx // strides[time_axis]) % sizes[time_axis]
            geo_code = geo_by_pos.get(geo_pos)
            year_str = time_by_pos.get(time_pos)
            if geo_code is None or year_str is None:
                continue
            try:
                year = int(year_str)
            except ValueError:
                # Pomijamy obserwacje miesięczne/kwartalne (np. "2020M01").
                continue

            # Eurostat używa "EL" dla Grecji i "UK" dla Wielkiej Brytanii —
            # mapujemy na standardowe kody ISO2.
            country_iso2 = {"EL": "GR", "UK": "GB"}.get(geo_code, geo_code)

            observations.append(
                EurostatObservation(
                    country_iso2=country_iso2,
                    year=year,
                    value=float(raw_value),
                )
            )

        return observations
