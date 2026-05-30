"""Testy jednostkowe klienta Eurostat — mockujemy httpx, sprawdzamy parsowanie JSON-stat."""
from __future__ import annotations

import httpx
import pytest

from app.ingestion.eurostat_client import EurostatClient, EurostatObservation
from app.ingestion.indicators_config import (
    EUROSTAT_INDICATORS,
    WORLDBANK_INDICATORS,
)


# Minimalna, ale realistyczna odpowiedź JSON-stat 2.0 z Eurostat:
# - 2 wymiary: geo (PL, DE) i time (2020, 2021), więc kostka 2x2 = 4 komórki,
# - wartości w sparse dict, brakująca wartość dla [DE, 2020].
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
    # idx = geo_pos * stride[geo] + time_pos * stride[time]
    # stride dla [2,2] = [2, 1]
    # PL,2020 -> 0*2+0*1 = 0
    # PL,2021 -> 0*2+1*1 = 1
    # DE,2020 -> 1*2+0*1 = 2  (POMINIĘTE — null)
    # DE,2021 -> 1*2+1*1 = 3
    "value": {
        "0": 15000.0,
        "1": 17000.0,
        "3": 44000.0,
    },
}


def _build_client(sample_payload: dict) -> EurostatClient:
    """Tworzy klient z mockowanym transportem httpx zwracającym zadany payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=sample_payload)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return EurostatClient(client=http_client)


def test_parse_jsonstat_extracts_observations():
    observations = EurostatClient._parse_jsonstat(SAMPLE_JSONSTAT)
    assert len(observations) == 3
    by_key = {(o.country_iso2, o.year): o.value for o in observations}
    assert by_key[("PL", 2020)] == 15000.0
    assert by_key[("PL", 2021)] == 17000.0
    assert by_key[("DE", 2021)] == 44000.0
    # Brakująca wartość (null) nie powinna być w wynikach.
    assert ("DE", 2020) not in by_key


def test_parse_jsonstat_skips_subannual_periods():
    """Eurostat potrafi zwrócić okresy kwartalne (2020Q1) lub miesięczne (2020M01) —
    powinny zostać pominięte, bo nasz model trzyma tylko lata całkowite."""
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
    """Eurostat używa 'EL' dla Grecji — klient mapuje to na ISO2 'GR'."""
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
