"""Testy normalizatora."""
from __future__ import annotations

import pytest

from app.ingestion.eurostat_client import EurostatObservation
from app.ingestion.worldbank_client import WorldBankObservation
from app.processing.normalizer import (
    ISO2_TO_ISO3,
    ISO3_TO_ISO2,
    iso2_to_iso3,
    normalize_country_code_iso2,
    normalize_eurostat_observations,
    normalize_value,
    normalize_worldbank_observations,
)


def test_normalize_iso2_passthrough():
    assert normalize_country_code_iso2("PL") == "PL"
    assert normalize_country_code_iso2("pl") == "PL"
    assert normalize_country_code_iso2(" de ") == "DE"


def test_normalize_eurostat_special_codes():
    assert normalize_country_code_iso2("EL") == "GR"
    assert normalize_country_code_iso2("UK") == "GB"


def test_normalize_iso3_to_iso2():
    assert normalize_country_code_iso2("POL") == "PL"
    assert normalize_country_code_iso2("DEU") == "DE"
    assert normalize_country_code_iso2("FRA") == "FR"


def test_normalize_empty_raises():
    with pytest.raises(ValueError):
        normalize_country_code_iso2("")


def test_normalize_unknown_raises():
    with pytest.raises(ValueError):
        normalize_country_code_iso2("XYZ")


def test_iso2_iso3_bidirectional_mapping_is_consistent():
    for iso3, iso2 in ISO3_TO_ISO2.items():
        assert ISO2_TO_ISO3[iso2] == iso3


def test_iso2_to_iso3_known():
    assert iso2_to_iso3("PL") == "POL"
    assert iso2_to_iso3("DE") == "DEU"


def test_iso2_to_iso3_unknown_raises():
    with pytest.raises(ValueError):
        iso2_to_iso3("ZZ")


def test_all_27_eu_countries_in_iso_maps():
    expected = {
        "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
        "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
        "NL", "PL", "PT", "RO", "SE", "SI", "SK",
    }
    assert set(ISO2_TO_ISO3.keys()) == expected


def test_normalize_value_rounds_to_four_decimals():
    assert normalize_value(3.14159265) == 3.1416
    assert normalize_value(1.0) == 1.0
    assert normalize_value(1.23456789, precision=2) == 1.23


def test_normalize_eurostat_maps_el_to_gr():
    obs = [
        EurostatObservation("EL", 2020, 19_000.123456789),
        EurostatObservation("PL", 2020, 15_000.0),
    ]
    out, report = normalize_eurostat_observations(obs)
    codes = {o.country_iso2 for o in out}
    assert "GR" in codes
    assert "EL" not in codes
    assert report.country_codes_normalized == 1
    gr_obs = next(o for o in out if o.country_iso2 == "GR")
    assert gr_obs.value == 19_000.1235


def test_normalize_worldbank_only_rounds():
    obs = [
        WorldBankObservation("POL", 2020, 15_678.123456789),
        WorldBankObservation("DEU", 2020, 45_000.0),
    ]
    out, report = normalize_worldbank_observations(obs)
    assert report.values_rounded == 1
    assert out[0].value == 15_678.1235
    assert out[1].value == 45_000.0
