# 0. 모듈 불러오기
from datetime import date
from enum import Enum

from pydantic import Field, field_validator

from backend.models.common import ApiModel
from backend.models.country import CountrySummary


# 1. 지원하는 사용자 유형
class Persona(str, Enum):
    STUDENT_TEAM = "대학생 팀"
    STARTUP = "스타트업"
    PUBLIC_ORGANIZATION = "공공기관·지자체"
    ESG_TEAM = "기업 ESG팀"
    JOB_SEEKER = "청년 구직자"


# 2. 지원하는 분석 분야
class AnalysisField(str, Enum):
    EDUCATION = "교육"
    HEALTH = "보건"
    DIGITAL = "디지털"
    CLIMATE = "기후·환경"
    CULTURE = "문화·한류"
    YOUTH_EMPLOYMENT = "청년취업"


# 3. 협력기회 분석 요청 모델과 ISO3 코드 정규화
class AnalysisRequest(ApiModel):
    country_iso3: str = Field(min_length=3, max_length=3)
    persona: Persona
    field: AnalysisField
    capabilities: list[str] = Field(default_factory=list, max_length=10)

    # 3.1. 입력된 국가 코드를 공백 없는 ISO3 대문자로 통일
    @field_validator("country_iso3")
    @classmethod
    def normalize_iso3(cls, value: str):
        return value.strip().upper()


# 4. 종합점수와 점수 등급 모델
class AnalysisSummary(ApiModel):
    persona: Persona
    field: AnalysisField
    score: float = Field(ge=0, le=100)
    score_level: str


# 5. 세부 평가지표 모델
class Metric(ApiModel):
    code: str
    name: str
    score: int = Field(ge=0, le=100)


# 6. 연도별 협력 신호 모델
class TrendPoint(ApiModel):
    year: int
    score: int = Field(ge=0, le=100)


# 7. 분석 근거와 원문 출처 모델
class EvidenceItem(ApiModel):
    evidence_id: str
    title: str
    category: str
    source: str
    reference_date: date
    source_url: str
    is_demo: bool


# 8. 국가별 주의 요인 모델
class RiskItem(ApiModel):
    title: str
    level: str
    score: int = Field(ge=0, le=100)
    source: str
    source_url: str


# 9. 데이터 완전성과 시범 데이터 여부 모델
class DataStatus(ApiModel):
    completeness: int = Field(ge=0, le=100)
    reference_date: date
    is_demo: bool
    notice: str


# 10. 화면과 PDF에서 사용하는 전체 분석 응답 모델
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
