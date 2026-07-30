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
from backend.services.openai_report_client import (
    OpenAIReportError,
    OpenAIReportGenerator,
)


PROMPT_VERSION = "report-rag-v2"
REPORT_SECTION_NAMES = (
    "project_title",
    "background",
    "local_demand",
    "korean_capabilities",
    "target_beneficiaries",
    "partner_types",
    "implementation_steps",
    "risks",
    "additional_checks",
)


def build_report(
    country: CountryRecord,
    request: ReportRequest,
    *,
    analysis_repo=None,
    report_repo=None,
    report_generator=None,
):
    analysis_repo = analysis_repo or analysis_repository
    report_repo = report_repo or report_repository
    generator = report_generator or OpenAIReportGenerator.from_environment()
    analysis_request = AnalysisRequest(**request.model_dump())
    analysis = build_analysis(country, analysis_request, repository=analysis_repo)
    request_hash = _build_request_hash(request, analysis)

    cached_payload = report_repo.get(request_hash)
    cached = (
        ReportResponse.model_validate(cached_payload)
        if cached_payload is not None
        else None
    )
    if cached is not None and _can_reuse_cache(cached, generator):
        return _as_cached(cached)

    sources = [
        ReportSource(**item.model_dump(mode="python"))
        for item in analysis.evidence
        if item.source_url
    ]
    if not sources:
        return _blocked_report(request, analysis, request_hash)

    if generator.is_configured:
        try:
            draft = generator.generate(_build_llm_context(request, analysis, sources))
            response = _build_llm_report(
                request,
                analysis,
                sources,
                draft,
                request_hash,
                generator.model,
            )
        except (OpenAIReportError, ValueError):
            if cached is not None:
                return _as_cached(
                    cached,
                    prefix="AI 연결 또는 출처 검증에 실패해 ",
                )
            return _build_rule_based_report(
                request,
                analysis,
                sources,
                request_hash,
                api_failed=True,
            )
        report_repo.save(request, response)
        return response

    response = _build_rule_based_report(
        request,
        analysis,
        sources,
        request_hash,
    )
    report_repo.save(request, response)
    return response


def _build_llm_context(request, analysis, sources):
    """LLM에 일반 지식 대신 검색·계산된 자료만 전달한다."""
    return {
        "request": request.model_dump(mode="json"),
        "analysis": {
            "country": analysis.country.model_dump(mode="json"),
            "score": analysis.analysis.model_dump(mode="json"),
            "metrics": [item.model_dump(mode="json") for item in analysis.metrics],
            "trend": [item.model_dump(mode="json") for item in analysis.trend],
            "risks": [item.model_dump(mode="json") for item in analysis.risks],
            "data_status": analysis.data_status.model_dump(mode="json"),
        },
        "evidence": [source.model_dump(mode="json") for source in sources],
    }


def _build_llm_report(
    request,
    analysis,
    sources,
    draft,
    request_hash,
    model_name,
):
    allowed_ids = {source.evidence_id for source in sources}
    citations = {}
    for name in REPORT_SECTION_NAMES:
        section = getattr(draft, name)
        citations[name] = _validate_evidence_ids(section.evidence_ids, allowed_ids)

    cited_ids = {
        evidence_id
        for section_ids in citations.values()
        for evidence_id in section_ids
    }
    cited_sources = [
        source for source in sources if source.evidence_id in cited_ids
    ]
    if not cited_sources:
        raise ValueError("The generated report cited no retrieved evidence")

    return ReportResponse(
        status="generated",
        generation_mode="llm",
        request_hash=request_hash,
        prompt_version=PROMPT_VERSION,
        generated_at=datetime.now(timezone.utc),
        country=analysis.country,
        persona=request.persona,
        field=request.field,
        project_title=draft.project_title.text,
        background=draft.background.text,
        local_demand=draft.local_demand.text,
        korean_capabilities=draft.korean_capabilities.text,
        target_beneficiaries=draft.target_beneficiaries.items,
        partner_types=draft.partner_types.items,
        implementation_steps=draft.implementation_steps.items,
        risks=draft.risks.items,
        additional_checks=draft.additional_checks.items,
        sources=cited_sources,
        data_status=analysis.data_status,
        notice=(
            "검색된 공공데이터와 계산 결과만 전달해 생성한 초기 검토안입니다. "
            "각 항목의 citations와 연결된 원문을 확인한 뒤 활용해야 합니다."
        ),
        citations=citations,
        llm_model=model_name,
    )


def _validate_evidence_ids(evidence_ids, allowed_ids):
    unique_ids = list(dict.fromkeys(evidence_ids))
    if not unique_ids:
        raise ValueError("Every generated section must cite evidence")
    unknown_ids = set(unique_ids) - allowed_ids
    if unknown_ids:
        raise ValueError("Generated report cited evidence outside the retrieved context")
    return unique_ids


def _build_rule_based_report(
    request,
    analysis,
    sources,
    request_hash,
    *,
    api_failed=False,
):
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
    source_ids = [source.evidence_id for source in sources[:3]]
    citations = {name: list(source_ids) for name in REPORT_SECTION_NAMES}
    failure_notice = (
        "OpenAI 연결 또는 응답 검증에 실패하여 " if api_failed else ""
    )

    return ReportResponse(
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
            failure_notice
            + "규칙 기반 초기 검토안을 반환했습니다. 시범 콘텐츠가 포함될 수 있으므로 "
            "원문과 최신 현지 정보를 다시 확인해야 합니다."
        ),
        citations=citations,
        llm_model=None,
    )


def _can_reuse_cache(cached, generator):
    if cached.generation_mode == "llm":
        return not generator.is_configured or cached.llm_model == generator.model
    return not generator.is_configured


def _as_cached(cached, prefix=""):
    return cached.model_copy(
        update={
            "status": "cached",
            "notice": (
                prefix
                + "동일한 조건과 근거로 저장된 검토안을 반환했습니다. "
                + cached.notice
            ),
        }
    )


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
        citations={},
        llm_model=None,
    )
