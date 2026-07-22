from datetime import date
from enum import Enum

from pydantic import Field, field_validator

from backend.models.common import ApiModel
from backend.models.country import CountrySummary


class Persona(str, Enum):
    STUDENT_TEAM = "대학생 팀"
    STARTUP = "스타트업"
    PUBLIC_ORGANIZATION = "공공기관·지자체"
    ESG_TEAM = "기업 ESG팀"
    JOB_SEEKER = "청년 구직자"


class AnalysisField(str, Enum):
    EDUCATION = "교육"
    HEALTH = "보건"
    DIGITAL = "디지털"
    CLIMATE = "기후·환경"
    CULTURE = "문화·한류"
    YOUTH_EMPLOYMENT = "청년취업"


class AnalysisRequest(ApiModel):
    country_iso3: str = Field(min_length=3, max_length=3)
    persona: Persona
    field: AnalysisField
    capabilities: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("country_iso3")
    @classmethod
    def normalize_iso3(cls, value: str):
        return value.strip().upper()


class AnalysisSummary(ApiModel):
    persona: Persona
    field: AnalysisField
    score: float = Field(ge=0, le=100)
    score_level: str


class Metric(ApiModel):
    code: str
    name: str
    score: int = Field(ge=0, le=100)


class TrendPoint(ApiModel):
    year: int
    score: int = Field(ge=0, le=100)


class EvidenceItem(ApiModel):
    title: str
    category: str
    source: str
    reference_date: date
    source_url: str
    is_demo: bool


class RiskItem(ApiModel):
    title: str
    level: str
    score: int = Field(ge=0, le=100)
    source: str
    source_url: str


class DataStatus(ApiModel):
    completeness: int = Field(ge=0, le=100)
    reference_date: date
    is_demo: bool
    notice: str


class AnalysisResponse(ApiModel):
    country: CountrySummary
    analysis: AnalysisSummary
    project_title: str
    interpretation: str
    partner_types: str
    sdgs: str
    metrics: list[Metric]
    trend: list[TrendPoint]
    evidence: list[EvidenceItem]
    recommendations: list[str]
    risks: list[RiskItem]
    gap_opportunity: str
    capabilities: list[str]
    data_status: DataStatus
