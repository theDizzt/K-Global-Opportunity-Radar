from datetime import date

from pydantic import Field

from backend.models.common import ApiModel


class CountrySummary(ApiModel):
    iso3: str = Field(pattern=r"^[A-Z]{3}$")
    name: str
    english_name: str
    region: str
    flag: str
    data_completeness: int = Field(ge=0, le=100)
    reference_date: date


class IndicatorValues(ApiModel):
    diplomacy: int = Field(ge=0, le=100)
    oda: int = Field(ge=0, le=100)
    korean_base: int = Field(ge=0, le=100)
    people_exchange: int = Field(ge=0, le=100)
    esg: int = Field(ge=0, le=100)


class CountryDetail(CountrySummary):
    indicators: IndicatorValues
    risk_level: str
    risk_score: int = Field(ge=0, le=100)
    focus_fields: list[str]
    gap_opportunity: str
    summary: str
