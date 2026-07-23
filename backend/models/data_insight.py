# 0. 모듈 불러오기
from datetime import datetime

from pydantic import Field

from backend.models.analysis import AnalysisField
from backend.models.common import ApiModel


# 1. 최근 수집 실행과 현재 적재량을 함께 보여주는 상태 모델
class CollectionStatusResponse(ApiModel):
    source_code: str
    latest_collected_at: datetime | None
    latest_status: str
    latest_record_count: int = Field(ge=0)
    latest_message: str | None
    stored_documents: int = Field(ge=0)
    covered_countries: int = Field(ge=0)
    datasets: dict[str, int]


# 2. 국가별 수집 문서의 누락·분류 상태를 점검하는 품질 모델
class CountryDataQualityResponse(ApiModel):
    country_iso3: str = Field(pattern=r"^[A-Z]{3}$")
    total_documents: int = Field(ge=0)
    dated_documents: int = Field(ge=0)
    summarized_documents: int = Field(ge=0)
    shared_documents: int = Field(ge=0)
    date_completeness: float = Field(ge=0, le=100)
    summary_completeness: float = Field(ge=0, le=100)
    datasets: dict[str, int]
    fields: dict[str, int]
    warnings: list[str]


# 3. 원문 근거 목록에 사용하는 문서 모델
class SourceDocumentItem(ApiModel):
    title: str
    summary: str
    dataset_code: str
    primary_field: str
    published_date: str | None
    source_url: str


# 4. 연도별 협력 신호와 정책 정합성 원시지표 모델
class RawSignalPoint(ApiModel):
    year: int
    document_count: int = Field(ge=0)
    matched_document_count: int = Field(ge=0)
    cooperation_signal: float = Field(ge=0)
    policy_alignment: float = Field(ge=0, le=100)


# 5. 국가·분야별 원시지표 산식 정보와 연도별 결과 모델
class CountrySignalsResponse(ApiModel):
    country_iso3: str = Field(pattern=r"^[A-Z]{3}$")
    field: AnalysisField
    formula_version: str
    formula_notice: str
    points: list[RawSignalPoint]
