# 0. 모듈 불러오기
from datetime import date

from pydantic import Field

from backend.models.common import ApiModel


# 1. 국가 목록에 사용하는 요약정보 모델
class CountrySummary(ApiModel):
    iso3: str = Field(pattern=r"^[A-Z]{3}$")
    name: str
    english_name: str
    region: str
    flag: str
    data_completeness: int = Field(ge=0, le=100)
    reference_date: date


# 2. 국가별 원천 평가지표 모델
class IndicatorValues(ApiModel):
    diplomacy: int = Field(ge=0, le=100)
    oda: int = Field(ge=0, le=100)
    korean_base: int = Field(ge=0, le=100)
    people_exchange: int = Field(ge=0, le=100)
    esg: int = Field(ge=0, le=100)


# 3. 국가 요약정보와 평가지표를 결합한 상세정보 모델
class CountryDetail(CountrySummary):
    indicators: IndicatorValues
    risk_level: str
    risk_score: int = Field(ge=0, le=100)
    focus_fields: list[str]
    gap_opportunity: str
    summary: str
