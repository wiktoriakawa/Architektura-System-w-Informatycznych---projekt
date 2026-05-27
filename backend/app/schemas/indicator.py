"""Schematy request/response dla wskaźników."""
from pydantic import BaseModel, Field


class IndicatorOut(BaseModel):
    id: int
    code: str = Field(examples=["gdp_per_capita_wb"])
    name: str = Field(examples=["GDP per capita (World Bank)"])
    unit: str | None = Field(default=None, examples=["current USD"])
    source: str | None = Field(default=None, examples=["worldbank"])

    model_config = {"from_attributes": True}
