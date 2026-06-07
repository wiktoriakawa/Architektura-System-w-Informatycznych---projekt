"""Normalizacja kodów krajów i wartości liczbowych."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


# Eurostat używa nietypowych kodów: EL=Greece (ISO: GR), UK=United Kingdom (ISO: GB).
EUROSTAT_TO_ISO2: dict[str, str] = {
    "EL": "GR",
    "UK": "GB",
}

# Mapa ISO3 -> ISO2 dla 27 krajów UE.
ISO3_TO_ISO2: dict[str, str] = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "CYP": "CY", "CZE": "CZ",
    "DEU": "DE", "DNK": "DK", "EST": "EE", "ESP": "ES", "FIN": "FI",
    "FRA": "FR", "GRC": "GR", "HRV": "HR", "HUN": "HU", "IRL": "IE",
    "ITA": "IT", "LTU": "LT", "LUX": "LU", "LVA": "LV", "MLT": "MT",
    "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO", "SWE": "SE",
    "SVN": "SI", "SVK": "SK",
}
ISO2_TO_ISO3: dict[str, str] = {v: k for k, v in ISO3_TO_ISO2.items()}

VALUE_PRECISION = 4


def normalize_country_code_iso2(raw_code: str) -> str:
    """ISO2 / ISO3 / kody Eurostatu → standard ISO2."""
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
    code = iso2_code.strip().upper()
    if code not in ISO2_TO_ISO3:
        raise ValueError(f"Unknown ISO2 code (not in EU set): {iso2_code!r}")
    return ISO2_TO_ISO3[code]


def normalize_value(value: float, precision: int = VALUE_PRECISION) -> float:
    return round(float(value), precision)


@dataclass
class NormalizationReport:
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
