"""Czyszczenie obserwacji — walidacja zakresów + wykrywanie outlierów IQR."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Protocol


class _ObservationLike(Protocol):
    year: int
    value: float


@dataclass(frozen=True)
class ValidationRule:
    min_value: float | None = None
    max_value: float | None = None
    description: str = ""


# Reguły domenowe — wartości spoza zakresu są fizycznie niemożliwe.
VALIDATION_RULES: dict[str, ValidationRule] = {
    "gdp_per_capita_eur": ValidationRule(0, 500_000, "PKB per capita EUR"),
    "gdp_per_capita_usd": ValidationRule(0, 500_000, "PKB per capita USD"),
    "unemployment_rate_eu": ValidationRule(0, 100, "Stopa bezrobocia %"),
    "unemployment_rate_wb": ValidationRule(0, 100, "Stopa bezrobocia %"),
    "population_total_eu": ValidationRule(0, 200_000_000, "Populacja kraju UE"),
    "life_expectancy": ValidationRule(30, 120, "Długość życia w latach"),
    "inflation_cpi": ValidationRule(-50, 10_000, "Inflacja CPI %"),
}

# Konserwatywny próg IQR — k=1.5 byłoby zbyt agresywne dla krótkich serii.
IQR_K = 3.0


@dataclass
class CleaningReport:
    received: int = 0
    kept: int = 0
    dropped_invalid_value: int = 0
    dropped_out_of_range: int = 0
    dropped_outlier_iqr: int = 0
    dropped_by_indicator: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def as_dict(self) -> dict:
        return {
            "received": self.received,
            "kept": self.kept,
            "dropped_invalid_value": self.dropped_invalid_value,
            "dropped_out_of_range": self.dropped_out_of_range,
            "dropped_outlier_iqr": self.dropped_outlier_iqr,
            "dropped_by_indicator": dict(self.dropped_by_indicator),
        }


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        raise ValueError("Cannot compute percentile of empty list")
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _detect_iqr_outliers(values: list[float], k: float = IQR_K) -> set[int]:
    # Serie < 5 punktów — IQR nie ma sensu statystycznego.
    if len(values) < 5:
        return set()
    sorted_vals = sorted(values)
    q1 = _percentile(sorted_vals, 25)
    q3 = _percentile(sorted_vals, 75)
    iqr = q3 - q1
    if iqr == 0:
        return set()
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    return {i for i, v in enumerate(values) if v < lower or v > upper}


def clean_observations(
    indicator_code: str,
    observations: Iterable[_ObservationLike],
) -> tuple[list, CleaningReport]:
    """Trzy etapy: odrzucenie nieprawidłowych → walidacja zakresu → outliery IQR per kraj."""
    obs_list = list(observations)
    report = CleaningReport(received=len(obs_list))
    rule = VALIDATION_RULES.get(indicator_code)

    # 1. None / NaN / inf
    valid: list = []
    for obs in obs_list:
        v = obs.value
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            report.dropped_invalid_value += 1
            report.dropped_by_indicator[indicator_code] += 1
            continue
        valid.append(obs)

    # 2. Zakres domenowy
    in_range: list = []
    for obs in valid:
        if rule is not None:
            if rule.min_value is not None and obs.value < rule.min_value:
                report.dropped_out_of_range += 1
                report.dropped_by_indicator[indicator_code] += 1
                continue
            if rule.max_value is not None and obs.value > rule.max_value:
                report.dropped_out_of_range += 1
                report.dropped_by_indicator[indicator_code] += 1
                continue
        in_range.append(obs)

    # 3. IQR per kraj
    def _country_key(obs) -> str:
        return getattr(obs, "country_iso2", None) or getattr(obs, "country_iso3", "")

    grouped: dict[str, list] = defaultdict(list)
    for obs in in_range:
        grouped[_country_key(obs)].append(obs)

    cleaned: list = []
    for country, items in grouped.items():
        values = [o.value for o in items]
        outlier_idx = _detect_iqr_outliers(values)
        for i, obs in enumerate(items):
            if i in outlier_idx:
                report.dropped_outlier_iqr += 1
                report.dropped_by_indicator[indicator_code] += 1
            else:
                cleaned.append(obs)

    report.kept = len(cleaned)
    return cleaned, report
