"""Klient World Bank Open Data API (v2)."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

import httpx
import structlog

from app.ingestion.indicators_config import IndicatorConfig

logger = structlog.get_logger()

WORLDBANK_BASE_URL = "https://api.worldbank.org/v2"
DEFAULT_TIMEOUT = 60.0
MAX_PAGE_SIZE = 20000
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 2.0


@dataclass(frozen=True)
class WorldBankObservation:
    country_iso3: str
    year: int
    value: float


class WorldBankClient:
    """Synchroniczny klient World Banku oparty na httpx."""

    def __init__(
        self,
        base_url: str = WORLDBANK_BASE_URL,
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
        countries_iso3: Iterable[str],
        year_from: int,
        year_to: int,
    ) -> list[WorldBankObservation]:
        if indicator.source != "worldbank":
            raise ValueError(f"Indicator {indicator.code} is not a World Bank indicator")

        countries_list = list(countries_iso3)
        if not countries_list:
            return []

        # WB przyjmuje wiele krajów oddzielonych średnikami.
        countries_path = ";".join(countries_list)
        url = f"{self.base_url}/country/{countries_path}/indicator/{indicator.dataset}"
        params = {
            "format": "json",
            "date": f"{year_from}:{year_to}",
            "per_page": str(MAX_PAGE_SIZE),
        }

        logger.info(
            "worldbank_request",
            indicator=indicator.code,
            wb_code=indicator.dataset,
            year_from=year_from,
            year_to=year_to,
            countries=countries_list,
        )

        payload = self._get_with_retry(url, params, indicator.code)
        observations = self._parse_response(payload)
        logger.info(
            "worldbank_response_parsed",
            indicator=indicator.code,
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
                    "worldbank_request_retry",
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

    def __enter__(self) -> "WorldBankClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @staticmethod
    def _parse_response(payload) -> list[WorldBankObservation]:
        """WB zwraca [meta, records]. Wyciągamy rekordy z wartościami != null."""
        if not isinstance(payload, list):
            raise ValueError("Unexpected World Bank response shape (not a list)")

        if len(payload) < 2 or not isinstance(payload[1], list):
            message = payload[0] if payload else {}
            raise ValueError(f"World Bank API returned no data: {message}")

        records = payload[1]
        observations: list[WorldBankObservation] = []
        for record in records:
            value = record.get("value")
            if value is None:
                continue
            iso3 = record.get("countryiso3code") or ""
            year_str = record.get("date") or ""
            if not iso3 or not year_str:
                continue
            try:
                year = int(year_str)
            except (TypeError, ValueError):
                continue
            try:
                value_f = float(value)
            except (TypeError, ValueError):
                continue

            observations.append(
                WorldBankObservation(
                    country_iso3=iso3.upper(),
                    year=year,
                    value=value_f,
                )
            )

        return observations
