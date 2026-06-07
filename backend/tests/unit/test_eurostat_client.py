"""Testy klienta Eurostat z mockowanym httpx."""
from __future__ import annotations

import httpx
import pytest

from app.ingestion.eurostat_client import EurostatClient, EurostatObservation
from app.ingestion.indicators_config import EUROSTAT_INDICATORS, WORLDBANK_INDICATORS


# 2 wymiary geo (PL, DE) x time (2020, 2021) = 4 komorki, jedna pominieta.
SAMPLE_JSONSTAT = {
    "version": "2.0",
    "class": "dataset",
    "label": "GDP per capita",
    "id": ["geo", "time"],
    "size": [2, 2],
    "dimension": {
        "geo": {
            "category": {
                "index": {"PL": 0, "DE": 1},
                "label": {"PL": "Poland", "DE": "Germany"},
            }
        },
        "time": {
            "category": {
                "index": {"2020": 0, "2021": 1},
                "label": {"2020": "2020", "2021": "2021"},
            }
        },
    },
    "value": {
        "0": 15000.0,  # PL, 2020
        "1": 17000.0,  # PL, 2021
        "3": 44000.0,  # DE, 2021 (DE 2020 pominiete)
    },
}


def _build_client(sample_payload: dict) -> EurostatClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=sample_payload)

    transport = httpx.MockTransport(handler)
    return EurostatClient(client=httpx.Client(transport=transport))


def test_parse_jsonstat_extracts_observations():
    observations = EurostatClient._parse_jsonstat(SAMPLE_JSONSTAT)
    assert len(observations) == 3
    by_key = {(o.country_iso2, o.year): o.value for o in observations}
    assert by_key[("PL", 2020)] == 15000.0
    assert by_key[("PL", 2021)] == 17000.0
    assert by_key[("DE", 2021)] == 44000.0
    assert ("DE", 2020) not in by_key


def test_parse_jsonstat_skips_subannual_periods():
    payload = {
        "version": "2.0",
        "id": ["geo", "time"],
        "size": [1, 2],
        "dimension": {
            "geo": {"category": {"index": {"PL": 0}, "label": {"PL": "Poland"}}},
            "time": {
                "category": {
                    "index": {"2020M01": 0, "2020": 1},
                    "label": {"2020M01": "2020M01", "2020": "2020"},
                }
            },
        },
        "value": {"0": 5.5, "1": 6.6},
    }
    observations = EurostatClient._parse_jsonstat(payload)
    assert observations == [EurostatObservation("PL", 2020, 6.6)]


def test_parse_jsonstat_handles_missing_geo_dimension():
    payload = {"id": ["time"], "size": [1], "dimension": {}, "value": {}}
    with pytest.raises(ValueError):
        EurostatClient._parse_jsonstat(payload)


def test_fetch_returns_parsed_observations():
    config = EUROSTAT_INDICATORS[0]
    client = _build_client(SAMPLE_JSONSTAT)
    observations = client.fetch(config, ["PL", "DE"], 2020, 2021)
    client.close()

    assert {(o.country_iso2, o.year) for o in observations} == {
        ("PL", 2020),
        ("PL", 2021),
        ("DE", 2021),
    }


def test_fetch_rejects_wrong_source():
    wb_config = WORLDBANK_INDICATORS[0]
    client = _build_client(SAMPLE_JSONSTAT)
    with pytest.raises(ValueError):
        client.fetch(wb_config, ["PL"], 2020, 2021)
    client.close()


def test_greek_country_code_normalised_to_gr():
    payload = {
        "id": ["geo", "time"],
        "size": [1, 1],
        "dimension": {
            "geo": {"category": {"index": {"EL": 0}, "label": {"EL": "Greece"}}},
            "time": {"category": {"index": {"2022": 0}, "label": {"2022": "2022"}}},
        },
        "value": {"0": 22000.0},
    }
    observations = EurostatClient._parse_jsonstat(payload)
    assert observations == [EurostatObservation("GR", 2022, 22000.0)]
