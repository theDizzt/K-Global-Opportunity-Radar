"""검색된 근거만 사용하는 초기 사업 검토안 조립 서비스."""

import hashlib
import json
import re
from datetime import datetime, timezone

from backend.models.analysis import AnalysisRequest
from backend.models.report import ReportRequest, ReportResponse, ReportSource
from backend.repositories.analysis_repository import analysis_repository
from backend.repositories.country_repository import CountryRecord
from backend.repositories.report_repository import report_repository
from backend.services.analysis_service import build_analysis


PROMPT_VERSION = "report-rule-v1"


def build_report(
    country: CountryRecord,
    request: ReportRequest,
    *,
    analysis_repo=None,
    report_repo=None,
):
    analysis_repo = analysis_repo or analysis_repository
    report_repo = report_repo or report_repository
    analysis_request = AnalysisRequest(**request.model_dump())
    analysis = build_analysis(country, analysis_request, repository=analysis_repo)
    request_hash = _build_request_hash(request, analysis)

    cached_payload = report_repo.get(request_hash)
    if cached_payload is not None:
        cached = ReportResponse.model_validate(cached_payload)
        return cached.model_copy(
            update={
                "status": "cached",
                "notice": (
                    "동일한 조건과 근거로 저장된 검토안을 반환했습니다. "
                    + cached.notice
                ),
            }
        )

    sources = [
        ReportSource(**item.model_dump(mode="python"))
        for item in analysis.evidence
        if item.source_url
    ]
    if not sources:
        return _blocked_report(request, analysis, request_hash)

    capabilities = [item.strip() for item in request.capabilities if item.strip()]
    partner_types = [
        item.strip()
        for item in re.split(r"[·,/]", analysis.partner_types)
        if item.strip()
    ]
    evidence_titles = "; ".join(source.title for source in sources[:3])
    risks = [item.title for item in analysis.risks]
    if not risks:
        risks = ["공개된 위험요인이 충분한지 추가 확인이 필요합니다."]

    response = ReportResponse(
        status="fallback",
        generation_mode="rule_based",
        request_hash=request_hash,
        prompt_version=PROMPT_VERSION,
        generated_at=datetime.now(timezone.utc),
        country=analysis.country,
        persona=request.persona,
        field=request.field,
        project_title=analysis.project_title,
        background=(
            f"{analysis.country.name}의 {request.field.value} 분야 협력 가능성을 "
            f"공개 근거 {len(sources)}건과 세부지표 {len(analysis.metrics)}개로 "
            "정리한 초기 검토안입니다."
        ),
        local_demand=f"공개 근거에서 확인된 검토 신호: {evidence_titles}",
        korean_capabilities=(
            "사용자가 입력한 한국 측 보유 역량 후보: " + ", ".join(capabilities)
            if capabilities
            else "한국 측에서 실제 활용 가능한 역량은 추가 확인이 필요합니다."
        ),
        target_beneficiaries=[
            "구체적인 최종 수혜자와 규모는 공개자료만으로 확인되지 않아 추가 확인이 필요합니다."
        ],
        partner_types=partner_types or ["현지 협력기관 유형 추가 확인 필요"],
        implementation_steps=[
            "연결된 원문에서 최신 현지 수요와 기존 유사사업을 재확인합니다.",
            "현지 협력기관의 참여 의사와 역할을 검증합니다.",
            "소규모 실증 범위와 성과지표를 합의한 뒤 추진 여부를 판단합니다.",
        ],
        risks=risks,
        additional_checks=[
            "기존 유사사업과의 중복 여부",
            "현지 협력기관의 실제 참여 의사",
            "사업 예산·법적 조건·개인정보 처리 요건",
            analysis.data_status.notice,
        ],
        sources=sources,
        data_status=analysis.data_status,
        notice=(
            "생성형 AI를 아직 호출하지 않은 규칙 기반 초기 검토안입니다. "
            "시범 콘텐츠가 포함될 수 있으므로 원문과 최신 현지 정보를 다시 확인해야 합니다."
        ),
    )
    report_repo.save(request, response)
    return response


def _build_request_hash(request, analysis):
    context = {
        "request": request.model_dump(mode="json"),
        "analysis": analysis.model_dump(mode="json"),
        "prompt_version": PROMPT_VERSION,
    }
    serialized = json.dumps(
        context,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _blocked_report(request, analysis, request_hash):
    message = "선택한 국가와 분야에 연결된 근거 문서가 없어 검토안 생성을 차단했습니다."
    return ReportResponse(
        status="blocked",
        generation_mode="none",
        request_hash=request_hash,
        prompt_version=PROMPT_VERSION,
        generated_at=datetime.now(timezone.utc),
        country=analysis.country,
        persona=request.persona,
        field=request.field,
        project_title="추가 확인 필요",
        background=message,
        local_demand="추가 확인 필요",
        korean_capabilities="추가 확인 필요",
        target_beneficiaries=["추가 확인 필요"],
        partner_types=["추가 확인 필요"],
        implementation_steps=["관련 공공데이터와 원문 자료를 먼저 확보합니다."],
        risks=["근거 부족으로 사실 기반 위험요인을 작성할 수 없습니다."],
        additional_checks=["국가·분야별 최신 원문 자료 확보"],
        sources=[],
        data_status=analysis.data_status,
        notice=message,
    )
