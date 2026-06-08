"""Testy jednostkowe klienta World Bank API — mockujemy httpx."""
from __future__ import annotations

import httpx
import pytest

from app.ingestion.indicators_config import EUROSTAT_INDICATORS, WORLDBANK_INDICATORS
from app.ingestion.worldbank_client import WorldBankClient, WorldBankObservation

SAMPLE_PAYLOAD = [
    {
        "page": 1,
        "pages": 1,
        "per_page": 20000,
        "total": 4,
        "sourceid": "2",
        "lastupdated": "2024-01-30",
    },
    [
        {
            "indicator": {"id": "NY.GDP.PCAP.CD", "value": "GDP per capita (current US$)"},
            "country": {"id": "PL", "value": "Poland"},
            "countryiso3code": "POL",
            "date": "2023",
            "value": 22345.6,
            "decimal": 1,
        },
        {
            "indicator": {"id": "NY.GDP.PCAP.CD", "value": "GDP per capita (current US$)"},
            "country": {"id": "DE", "value": "Germany"},
            "countryiso3code": "DEU",
            "date": "2023",
            "value": 51383.2,
            "decimal": 1,
        },
        {
            # Brakująca wartość — World Bank nie wymusza pełnego pokrycia lat.
            "indicator": {"id": "NY.GDP.PCAP.CD"},
            "country": {"id": "PL"},
            "countryiso3code": "POL",
            "date": "2022",
            "value": None,
            "decimal": 1,
        },
        {
            # Niepoprawny rok — pomijamy.
            "indicator": {"id": "NY.GDP.PCAP.CD"},
            "country": {"id": "PL"},
            "countryiso3code": "POL",
            "date": "NA",
            "value": 100.0,
            "decimal": 1,
        },
    ],
]


def _build_client(payload) -> WorldBankClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return WorldBankClient(client=http_client)


def test_fetch_parses_observations():
    config = WORLDBANK_INDICATORS[0]
    client = _build_client(SAMPLE_PAYLOAD)
    observations = client.fetch(config, ["POL", "DEU"], 2022, 2023)
    client.close()

    assert observations == [
        WorldBankObservation("POL", 2023, 22345.6),
        WorldBankObservation("DEU", 2023, 51383.2),
    ]


def test_fetch_returns_empty_for_no_countries():
    config = WORLDBANK_INDICATORS[0]
    client = _build_client(SAMPLE_PAYLOAD)
    assert client.fetch(config, [], 2020, 2023) == []
    client.close()


def test_fetch_rejects_wrong_source():
    eurostat_config = EUROSTAT_INDICATORS[0]
    client = _build_client(SAMPLE_PAYLOAD)
    with pytest.raises(ValueError):
        client.fetch(eurostat_config, ["POL"], 2020, 2023)
    client.close()


def test_error_payload_raises():
    error_payload = [
        {
            "message": [
                {"id": "120", "key": "Invalid value", "value": "The provided country is invalid"}
            ]
        }
    ]
    client = _build_client(error_payload)
    with pytest.raises(ValueError):
        client.fetch(WORLDBANK_INDICATORS[0], ["XYZ"], 2020, 2023)
    client.close()
