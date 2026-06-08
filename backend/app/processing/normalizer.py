"""
Moduł normalizacji danych — harmonizacja kodów krajów i wartości liczbowych.

Po co osobny moduł, skoro klient Eurostat już mapuje EL→GR i UK→GB?
  - Centralizujemy logikę w jednym miejscu (DRY) — gdyby pojawiło się kolejne
    źródło danych (np. OECD), korzysta z tej samej tabeli mapowań.
  - Mapujemy między ISO2 a ISO3 (potrzebne, bo Eurostat używa ISO2, a World
    Bank ISO3 — w bazie trzymamy oba, ale procesowanie wewnętrzne ujednolicamy).
  - Zaokrąglamy wartości do sensownej precyzji (4 miejsca po przecinku),
    żeby uniknąć "szumu zmiennoprzecinkowego" w bazie i UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


# ---------------------------------------------------------------------------
# Mapowania kodów krajów — odchylenia od standardu ISO 3166-1.
# ---------------------------------------------------------------------------
# Eurostat używa nietypowych kodów ISO2 dla dwóch państw:
#   EL = Greece (ISO: GR)
#   UK = United Kingdom (ISO: GB)
# Mapa konwersji z kodu źródłowego na nasz standard wewnętrzny (ISO2).
EUROSTAT_TO_ISO2: dict[str, str] = {
    "EL": "GR",
    "UK": "GB",
}

# Pełna mapa ISO3 → ISO2 dla 27 krajów UE (potrzebna, gdy mamy obserwację
# z World Bank, a chcemy znaleźć rekord kraju w bazie indeksowanej ISO2).
ISO3_TO_ISO2: dict[str, str] = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "CYP": "CY", "CZE": "CZ",
    "DEU": "DE", "DNK": "DK", "EST": "EE", "ESP": "ES", "FIN": "FI",
    "FRA": "FR", "GRC": "GR", "HRV": "HR", "HUN": "HU", "IRL": "IE",
    "ITA": "IT", "LTU": "LT", "LUX": "LU", "LVA": "LV", "MLT": "MT",
    "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO", "SWE": "SE",
    "SVN": "SI", "SVK": "SK",
}
ISO2_TO_ISO3: dict[str, str] = {v: k for k, v in ISO3_TO_ISO2.items()}

# Precyzja zaokrąglania wartości liczbowych (4 miejsca = 0.0001).
VALUE_PRECISION = 4


def normalize_country_code_iso2(raw_code: str) -> str:
    """Normalizuje surowy kod kraju do standardu ISO2.

    Obsługuje:
      - małe litery (`pl` → `PL`),
      - kody Eurostatu (`EL` → `GR`, `UK` → `GB`),
      - kody ISO3 (`POL` → `PL`).
    """
    if not raw_code:
        raise ValueError("Country code cannot be empty")
    code = raw_code.strip().upper()
    if code in EUROSTAT_TO_ISO2:
        return EUROSTAT_TO_ISO2[code]
    if len(code) == 3 and code in ISO3_TO_ISO2:
        return ISO3_TO_ISO2[code]
    if len(code) == 2:
        return code
    raise ValueError(f"Cannot normalise country code: {raw_code!r}")


def iso2_to_iso3(iso2_code: str) -> str:
    """Konwersja ISO2 → ISO3 dla krajów UE."""
    code = iso2_code.strip().upper()
    if code not in ISO2_TO_ISO3:
        raise ValueError(f"Unknown ISO2 code (not in EU set): {iso2_code!r}")
    return ISO2_TO_ISO3[code]


def normalize_value(value: float, precision: int = VALUE_PRECISION) -> float:
    """Zaokrąglenie wartości do zadanej precyzji."""
    return round(float(value), precision)


@dataclass
class NormalizationReport:
    """Statystyki normalizacji jednego batcha."""

    processed: int = 0
    country_codes_normalized: int = 0
    values_rounded: int = 0

    def as_dict(self) -> dict:
        return {
            "processed": self.processed,
            "country_codes_normalized": self.country_codes_normalized,
            "values_rounded": self.values_rounded,
        }


def normalize_eurostat_observations(observations: Iterable) -> tuple[list, NormalizationReport]:
    """Normalizuje obserwacje z Eurostatu (mutuje pola w razie potrzeby).

    Klient Eurostat już wstępnie mapuje EL/UK na ISO2, ale ten moduł działa
    jako bezpiecznik (defense in depth) — gdyby zmieniono klienta, dane wciąż
    będą poprawne. Operuje na obiektach immutable (dataclass frozen), więc
    tworzy nowe instancje przez `dataclasses.replace`.
    """
    from dataclasses import replace

    report = NormalizationReport()
    out = []
    for obs in observations:
        report.processed += 1
        country_iso2 = obs.country_iso2.upper()
        normalised_iso2 = EUROSTAT_TO_ISO2.get(country_iso2, country_iso2)
        rounded_value = normalize_value(obs.value)

        changes = {}
        if normalised_iso2 != obs.country_iso2:
            changes["country_iso2"] = normalised_iso2
            report.country_codes_normalized += 1
        if rounded_value != obs.value:
            changes["value"] = rounded_value
            report.values_rounded += 1

        out.append(replace(obs, **changes) if changes else obs)
    return out, report


def normalize_worldbank_observations(observations: Iterable) -> tuple[list, NormalizationReport]:
    """Normalizuje obserwacje z World Banku (zaokrąglenia wartości)."""
    from dataclasses import replace

    report = NormalizationReport()
    out = []
    for obs in observations:
        report.processed += 1
        rounded_value = normalize_value(obs.value)
        if rounded_value != obs.value:
            out.append(replace(obs, value=rounded_value))
            report.values_rounded += 1
        else:
            out.append(obs)
    return out, report
