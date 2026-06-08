"""Testy jednostkowe modułu czyszczenia danych."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.processing.cleaner import (
    CleaningReport,
    VALIDATION_RULES,
    _detect_iqr_outliers,
    _percentile,
    clean_observations,
)


@dataclass
class FakeObs:
    """Lekka obserwacja na potrzeby testów (zgodna z protokołem _ObservationLike)."""

    country_iso2: str
    year: int
    value: float


# ---------------------------------------------------------------------------
# Walidacja zakresów domenowych
# ---------------------------------------------------------------------------

def test_rejects_negative_unemployment():
    observations = [
        FakeObs("PL", 2020, 5.0),
        FakeObs("PL", 2021, -1.0),  # ujemne — niemożliwe
        FakeObs("PL", 2022, 6.5),
    ]
    cleaned, report = clean_observations("unemployment_rate_eu", observations)
    assert len(cleaned) == 2
    assert report.dropped_out_of_range == 1
    assert all(o.value >= 0 for o in cleaned)


def test_rejects_unemployment_above_100():
    observations = [
        FakeObs("PL", 2020, 50.0),
        FakeObs("PL", 2021, 150.0),  # > 100% niemożliwe
    ]
    cleaned, report = clean_observations("unemployment_rate_eu", observations)
    assert len(cleaned) == 1
    assert report.dropped_out_of_range == 1


def test_rejects_extreme_gdp():
    observations = [
        FakeObs("PL", 2020, 15_000),
        FakeObs("PL", 2021, 1_000_000),  # ponad max 500k
    ]
    cleaned, report = clean_observations("gdp_per_capita_usd", observations)
    assert len(cleaned) == 1
    assert report.dropped_out_of_range == 1


def test_accepts_inflation_negative_deflation():
    """Inflacja może być ujemna (deflacja) — minimum to -50%, nie 0."""
    observations = [
        FakeObs("PL", 2020, -2.5),  # deflacja
        FakeObs("PL", 2021, 8.0),
    ]
    cleaned, report = clean_observations("inflation_cpi", observations)
    assert len(cleaned) == 2
    assert report.dropped_out_of_range == 0


# ---------------------------------------------------------------------------
# Wartości "uszkodzone" (None, NaN, inf)
# ---------------------------------------------------------------------------

def test_rejects_nan_and_inf():
    observations = [
        FakeObs("PL", 2020, 5.0),
        FakeObs("PL", 2021, float("nan")),
        FakeObs("PL", 2022, float("inf")),
    ]
    cleaned, report = clean_observations("unemployment_rate_eu", observations)
    assert len(cleaned) == 1
    assert report.dropped_invalid_value == 2


# ---------------------------------------------------------------------------
# Wykrywanie outlierów IQR
# ---------------------------------------------------------------------------

def test_percentile_basic():
    assert _percentile([1, 2, 3, 4, 5], 50) == 3
    assert _percentile([1, 2, 3, 4, 5], 25) == 2
    assert _percentile([1, 2, 3, 4, 5], 75) == 4


def test_iqr_outliers_short_series_skipped():
    """Dla serii < 5 punktów IQR nie ma sensu statystycznego."""
    assert _detect_iqr_outliers([1.0, 2.0, 3.0, 4.0]) == set()


def test_iqr_outliers_detects_extreme_value():
    # Stabilny szereg z jednym ekstremalnym punktem.
    values = [10.0, 11.0, 10.5, 11.5, 10.8, 11.2, 10.3, 1000.0]
    outliers = _detect_iqr_outliers(values)
    assert 7 in outliers  # ostatni indeks (1000.0) to outlier


def test_iqr_outliers_on_indicator_pipeline():
    """Pełen flow: ekstremalna wartość PKB w jednym roku zostaje odrzucona jako outlier."""
    # Stabilna seria PKB Polski + jeden ekstremalny rok.
    obs = [
        FakeObs("PL", 2015, 12_000),
        FakeObs("PL", 2016, 12_500),
        FakeObs("PL", 2017, 13_000),
        FakeObs("PL", 2018, 13_500),
        FakeObs("PL", 2019, 14_000),
        FakeObs("PL", 2020, 14_500),
        FakeObs("PL", 2021, 15_000),
        FakeObs("PL", 2022, 400_000),  # outlier — błąd źródła
    ]
    cleaned, report = clean_observations("gdp_per_capita_usd", obs)
    assert report.dropped_outlier_iqr == 1
    assert all(o.value < 100_000 for o in cleaned)


# ---------------------------------------------------------------------------
# Sanity raportu
# ---------------------------------------------------------------------------

def test_report_counts_consistency():
    obs = [
        FakeObs("PL", 2020, 5.0),
        FakeObs("PL", 2021, -1.0),    # out of range
        FakeObs("PL", 2022, float("nan")),  # invalid
    ]
    cleaned, report = clean_observations("unemployment_rate_eu", obs)
    assert report.received == 3
    assert report.kept == len(cleaned) == 1
    assert (
        report.dropped_invalid_value
        + report.dropped_out_of_range
        + report.dropped_outlier_iqr
        + report.kept
        == report.received
    )


def test_all_seven_indicators_have_rules():
    """Każdy z naszych 7 wskaźników z konfiguracji musi mieć regułę walidacji."""
    from app.ingestion.indicators_config import ALL_INDICATORS

    for indicator in ALL_INDICATORS:
        assert indicator.code in VALIDATION_RULES, (
            f"Brak reguły walidacji dla {indicator.code}"
        )
