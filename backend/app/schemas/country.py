"""Schematy request/response dla krajów."""
from pydantic import BaseModel, Field


class CountryOut(BaseModel):
    id: int
    code_iso2: str = Field(examples=["PL"])
    code_iso3: str = Field(examples=["POL"])
    name: str = Field(examples=["Poland"])
    region: str | None = Field(default=None, examples=["EU"])

    model_config = {"from_attributes": True}
