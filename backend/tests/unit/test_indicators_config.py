"""Sanity checki konfiguracji wskaźników."""
from app.ingestion.indicators_config import (
    ALL_INDICATORS,
    EUROSTAT_INDICATORS,
    WORLDBANK_INDICATORS,
    get_indicator,
)


def test_all_indicators_have_unique_codes():
    codes = [i.code for i in ALL_INDICATORS]
    assert len(codes) == len(set(codes))


def test_source_classification():
    assert all(i.source == "eurostat" for i in EUROSTAT_INDICATORS)
    assert all(i.source == "worldbank" for i in WORLDBANK_INDICATORS)


def test_get_indicator_returns_known_code():
    indicator = get_indicator("gdp_per_capita_usd")
    assert indicator is not None
    assert indicator.source == "worldbank"


def test_get_indicator_returns_none_for_unknown_code():
    assert get_indicator("does_not_exist") is None


def test_at_least_two_sources_present():
    sources = {i.source for i in ALL_INDICATORS}
    assert sources == {"eurostat", "worldbank"}
