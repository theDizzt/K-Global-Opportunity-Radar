"""근거 기반 초기 사업 검토안 API 모델."""

from datetime import date, datetime
from typing import Literal

from backend.models.analysis import AnalysisField, AnalysisRequest, DataStatus, Persona
from backend.models.common import ApiModel
from backend.models.country import CountrySummary


class ReportRequest(AnalysisRequest):
    """분석 조건을 그대로 재사용하는 보고서 생성 요청."""


class ReportSource(ApiModel):
    evidence_id: str
    title: str
    category: str
    source: str
    reference_date: date
    source_url: str
    is_demo: bool


class ReportResponse(ApiModel):
    status: Literal["generated", "cached", "fallback", "blocked"]
    generation_mode: Literal["llm", "rule_based", "none"]
    request_hash: str
    prompt_version: str
    generated_at: datetime
    country: CountrySummary
    persona: Persona
    field: AnalysisField
    project_title: str
    background: str
    local_demand: str
    korean_capabilities: str
    target_beneficiaries: list[str]
    partner_types: list[str]
    implementation_steps: list[str]
    risks: list[str]
    additional_checks: list[str]
    sources: list[ReportSource]
    data_status: DataStatus
    notice: str
