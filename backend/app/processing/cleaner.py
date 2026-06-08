"""
Moduł czyszczenia danych — walidacja zakresów + wykrywanie outlierów.

Cel:
  - Odrzucenie obserwacji niemożliwych z natury wskaźnika (np. bezrobocie > 100%,
    ujemna populacja, ujemna długość życia).
  - Wykrywanie statystycznych outlierów dla każdej serii czasowej (kraj × wskaźnik)
    metodą rozstępu międzykwartylowego (IQR).

Cleaner zwraca:
  - listę "czystych" obserwacji do dalszego przetwarzania,
  - obiekt `CleaningReport` z licznikami odrzuceń per powód.

Wszystkie reguły są jawnie skonfigurowane w `VALIDATION_RULES` (dict keyowany
kodem wskaźnika) — łatwo audytować i rozszerzać.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Protocol


# Wspólny "kształt" obserwacji z obu źródeł (Eurostat / WorldBank) — używamy
# Protocol, żeby nie wprowadzać sztywnej zależności na konkretną klasę.
class _ObservationLike(Protocol):
    year: int
    value: float


@dataclass(frozen=True)
class ValidationRule:
    """Pojedyncza reguła walidacji wartości wskaźnika."""

    min_value: float | None = None
    max_value: float | None = None
    description: str = ""


# ---------------------------------------------------------------------------
# Reguły domenowe — pochodzą z natury każdego wskaźnika.
# Wartości spoza zakresu odrzucamy, bo są fizycznie niemożliwe lub świadczą
# o błędzie w źródłowych danych.
# ---------------------------------------------------------------------------
VALIDATION_RULES: dict[str, ValidationRule] = {
    "gdp_per_capita_eur": ValidationRule(
        min_value=0,
        max_value=500_000,
        description="PKB per capita w EUR — realnie 0–500k.",
    ),
    "gdp_per_capita_usd": ValidationRule(
        min_value=0,
        max_value=500_000,
        description="PKB per capita w USD — realnie 0–500k.",
    ),
    "unemployment_rate_eu": ValidationRule(
        min_value=0,
        max_value=100,
        description="Stopa bezrobocia w % — z definicji 0–100.",
    ),
    "unemployment_rate_wb": ValidationRule(
        min_value=0,
        max_value=100,
        description="Stopa bezrobocia w % — z definicji 0–100.",
    ),
    "population_total_eu": ValidationRule(
        min_value=0,
        max_value=200_000_000,
        description="Populacja kraju UE — żaden kraj nie przekroczy 200 mln.",
    ),
    "life_expectancy": ValidationRule(
        min_value=30,
        max_value=120,
        description="Oczekiwana długość życia — realnie 30–120 lat.",
    ),
    "inflation_cpi": ValidationRule(
        min_value=-50,
        max_value=10_000,
        description="Inflacja CPI rok do roku — od deflacji do hiperinflacji.",
    ),
}


# Próg IQR — punkt jest outlierem, gdy leży poza [Q1 - K*IQR, Q3 + K*IQR].
# Wartość 3.0 jest konserwatywna (większa = mniej odrzuceń); klasyczne 1.5
# byłoby zbyt agresywne dla krótkich serii czasowych ekonomicznych.
IQR_K = 3.0


@dataclass
class CleaningReport:
    """Statystyki czyszczenia jednego batcha obserwacji."""

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
    """Liniowa interpolacja percentyla (jak numpy.percentile, ale bez numpy)."""
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
    """Zwraca indeksy wartości, które są outlierami wg metody IQR.

    Dla serii < 5 punktów IQR nie ma sensu statystycznego — nie wykrywamy outlierów.
    """
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
    """
    Czyści obserwacje dla pojedynczego wskaźnika.

    Etapy:
      1. Odrzuca obserwacje z `None`, `NaN`, `inf` (dane uszkodzone).
      2. Odrzuca obserwacje poza zakresem domenowym (`VALIDATION_RULES`).
      3. Wykrywa outliery IQR per kraj (jeśli obserwacje mają atrybut country_iso2/iso3).

    Zwraca: (lista_czystych_obserwacji, raport).
    """
    import math

    obs_list = list(observations)
    report = CleaningReport(received=len(obs_list))
    rule = VALIDATION_RULES.get(indicator_code)

    # ---- Etap 1: odrzucenie wartości nieprawidłowych (None, NaN, inf) ----
    valid: list = []
    for obs in obs_list:
        v = obs.value
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            report.dropped_invalid_value += 1
            report.dropped_by_indicator[indicator_code] += 1
            continue
        valid.append(obs)

    # ---- Etap 2: walidacja zakresu domenowego ----
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

    # ---- Etap 3: IQR per kraj (jeśli obserwacje mają identyfikator kraju) ----
    # Grupujemy po dowolnym atrybucie kraju, który obserwacja udostępnia.
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
