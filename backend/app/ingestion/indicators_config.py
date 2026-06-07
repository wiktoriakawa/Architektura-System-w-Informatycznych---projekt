"""Konfiguracja wskaźników pobieranych z Eurostat i World Bank."""
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class IndicatorConfig:
    code: str
    name: str
    unit: str
    source: Literal["eurostat", "worldbank"]
    dataset: str
    filters: dict[str, str] = field(default_factory=dict)


EUROSTAT_INDICATORS: list[IndicatorConfig] = [
    IndicatorConfig(
        code="gdp_per_capita_eur",
        name="PKB per capita (Eurostat)",
        unit="EUR per mieszkańca (ceny bieżące)",
        source="eurostat",
        dataset="nama_10_pc",
        filters={"unit": "CP_EUR_HAB", "na_item": "B1GQ"},
    ),
    IndicatorConfig(
        code="unemployment_rate_eu",
        name="Stopa bezrobocia (Eurostat)",
        unit="% aktywnych zawodowo (15-74)",
        source="eurostat",
        dataset="une_rt_a",
        filters={"unit": "PC_ACT", "sex": "T", "age": "Y15-74"},
    ),
    IndicatorConfig(
        code="population_total_eu",
        name="Populacja (Eurostat, 1 stycznia)",
        unit="osoby",
        source="eurostat",
        dataset="demo_pjan",
        filters={"sex": "T", "age": "TOTAL"},
    ),
]

WORLDBANK_INDICATORS: list[IndicatorConfig] = [
    IndicatorConfig(
        code="gdp_per_capita_usd",
        name="PKB per capita (World Bank)",
        unit="USD (ceny bieżące)",
        source="worldbank",
        dataset="NY.GDP.PCAP.CD",
    ),
    IndicatorConfig(
        code="life_expectancy",
        name="Oczekiwana długość życia",
        unit="lata",
        source="worldbank",
        dataset="SP.DYN.LE00.IN",
    ),
    IndicatorConfig(
        code="inflation_cpi",
        name="Inflacja CPI (rok do roku)",
        unit="%",
        source="worldbank",
        dataset="FP.CPI.TOTL.ZG",
    ),
    IndicatorConfig(
        code="unemployment_rate_wb",
        name="Stopa bezrobocia (World Bank, modelowane ILO)",
        unit="% siły roboczej",
        source="worldbank",
        dataset="SL.UEM.TOTL.ZS",
    ),
]


ALL_INDICATORS: list[IndicatorConfig] = EUROSTAT_INDICATORS + WORLDBANK_INDICATORS


def get_indicator(code: str) -> IndicatorConfig | None:
    return next((i for i in ALL_INDICATORS if i.code == code), None)
