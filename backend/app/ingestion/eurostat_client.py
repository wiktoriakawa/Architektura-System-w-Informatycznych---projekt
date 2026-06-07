"""Klient Eurostat REST API (SDMX 2.1, JSON-stat 2.0)."""
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
    country_iso2: str
    year: int
    value: float


class EurostatClient:
    """Synchroniczny klient Eurostatu oparty na httpx."""

    def __init__(
        self,
        base_url: str = EUROSTAT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    def fetch(
        self,
        indicator: IndicatorConfig,
        countries_iso2: Iterable[str],
        year_from: int,
        year_to: int,
    ) -> list[EurostatObservation]:
        if indicator.source != "eurostat":
            raise ValueError(f"Indicator {indicator.code} is not an Eurostat indicator")

        url = f"{self.base_url}/{indicator.dataset}"
        params: list[tuple[str, str]] = [("format", "JSON"), ("lang", "EN")]

        for key, value in indicator.filters.items():
            params.append((key, value))

        for country in countries_iso2:
            params.append(("geo", country))

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
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
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
        assert last_error is not None
        raise last_error

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "EurostatClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @staticmethod
    def _parse_jsonstat(payload: dict) -> list[EurostatObservation]:
        """Rozplata JSON-stat 2.0 do listy obserwacji (kraj, rok, wartość)."""
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
        geo_index = dim_data["geo"]["category"]["index"]
        time_index = dim_data["time"]["category"]["index"]
        geo_by_pos: dict[int, str] = {pos: code for code, pos in geo_index.items()}
        time_by_pos: dict[int, str] = {pos: code for code, pos in time_index.items()}

        # Stride dla wymiaru i = iloczyn rozmiarów na prawo od niego.
        strides: list[int] = [1] * len(sizes)
        for i in range(len(sizes) - 2, -1, -1):
            strides[i] = strides[i + 1] * sizes[i + 1]

        values = payload.get("value", {})
        observations: list[EurostatObservation] = []

        for raw_index, raw_value in values.items():
            if raw_value is None:
                continue
            idx = int(raw_index)
            geo_pos = (idx // strides[geo_axis]) % sizes[geo_axis]
            time_pos = (idx // strides[time_axis]) % sizes[time_axis]
            geo_code = geo_by_pos.get(geo_pos)
            year_str = time_by_pos.get(time_pos)
            if geo_code is None or year_str is None:
                continue
            try:
                year = int(year_str)
            except ValueError:
                # Pomijamy okresy miesięczne/kwartalne (2020M01, 2020Q1).
                continue

            # Eurostat: EL=Grecja, UK=UK — mapujemy na standardowe ISO2.
            country_iso2 = {"EL": "GR", "UK": "GB"}.get(geo_code, geo_code)

            observations.append(
                EurostatObservation(
                    country_iso2=country_iso2,
                    year=year,
                    value=float(raw_value),
                )
            )

        return observations
