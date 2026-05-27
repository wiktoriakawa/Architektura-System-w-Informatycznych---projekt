"""Schematy request/response dla punktów danych i porównań."""
from pydantic import BaseModel, Field


class DataPointOut(BaseModel):
    country: str = Field(description="Kod ISO2 kraju", examples=["PL"])
    country_name: str = Field(examples=["Poland"])
    year: int = Field(examples=[2023])
    value: float | None = Field(examples=[22345.6])


class IndicatorDataResponse(BaseModel):
    indicator: str = Field(description="Kod wskaźnika", examples=["gdp_per_capita_wb"])
    indicator_name: str = Field(examples=["GDP per capita (World Bank)"])
    unit: str | None = Field(examples=["current USD"])
    data: list[DataPointOut]
