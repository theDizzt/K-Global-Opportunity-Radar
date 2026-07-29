# 0. 모듈 불러오기
from backend.models.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisSummary,
    DataStatus,
    EvidenceItem,
    Metric,
    RiskItem,
    TrendPoint,
)
from backend.repositories.analysis_repository import analysis_repository
from backend.repositories.country_repository import CountryRecord
from services.scoring_service import (
    calculate_opportunity_score,
    calculate_score,
    get_analysis_metrics,
    get_opportunity_metrics,
    get_score_level,
)


# 1. 화면용 한글 지표명과 API 지표 코드 연결
METRIC_CODES = {
    "수요성": "demand",
    "정책 정합성": "policy_alignment",
    "한국 연계기반": "korean_base",
    "실행 준비도": "readiness",
}

# 2. 시범 데이터 사용 사실과 재확인 안내 문구
DATA_NOTICE = (
    "현재 응답은 화면과 추천 흐름을 검증하기 위한 시범 정제 데이터입니다. "
    "실제 사업 결정 전 최신 원문과 현지 정보를 다시 확인해야 합니다."
)
LIVE_DATA_NOTICE = (
    "기회점수와 세부지표는 수집·정제된 공공데이터로 계산했습니다. "
    "대표 프로젝트와 협력모델 문구는 아직 화면 검증용 시범 콘텐츠이므로 "
    "실제 사업 결정 전 원문과 현지 정보를 다시 확인해야 합니다."
)


# 3. 국가정보와 사용자 요청을 결합하여 전체 분석 응답 생성
def build_analysis(country: CountryRecord, request: AnalysisRequest, repository=None):
    repository = repository or analysis_repository
    # 3.1. 실제 점수가 있으면 우선 사용하고 없을 때만 시범 산식으로 폴백
    persona = request.persona.value
    field = request.field.value
    opportunity = repository.get_opportunity_score(country.iso3, field)
    if opportunity is None:
        score = calculate_score(country, persona, field)
        raw_metrics = get_analysis_metrics(country, field)
        history = repository.get_signal_history(country.iso3)
        country_summary = country.to_summary()
    else:
        score = calculate_opportunity_score(opportunity, persona)
        raw_metrics = get_opportunity_metrics(opportunity)
        history = repository.get_opportunity_history(country.iso3, field)
        country_summary = country.to_summary().model_copy(
            update={
                "data_completeness": round(opportunity.data_confidence),
                "reference_date": opportunity.as_of_date,
            }
        )

    metrics = [
        Metric(code=METRIC_CODES[name], name=name, score=value)
        for name, value, _, _ in raw_metrics
    ]
    # 3.2. 저장된 연도별 추세의 최신값을 사용자 유형 적용 점수로 갱신
    trend_values = [value for _, value in history]
    if trend_values:
        trend_values[-1] = round(score)
    trend = [
        TrendPoint(year=year, score=value)
        for (year, _), value in zip(history, trend_values, strict=True)
    ]
    # 3.3. 저장소의 근거와 주의 요인을 API 응답 모델로 변환
    evidence_records = repository.get_evidence(country.iso3, field)
    evidence = [
        EvidenceItem(
            evidence_id=item.evidence_id,
            title=item.title,
            category=item.category,
            source=item.source,
            reference_date=item.reference_date,
            source_url=item.source_url,
            is_demo=item.is_demo,
        )
        for item in evidence_records
    ]
    risks = [
        RiskItem(
            title=item.title,
            level=item.level,
            score=item.score,
            source=item.source,
            source_url=item.source_url,
        )
        for item in repository.get_risks(country.iso3)
    ]
    # 3.4. 프로젝트와 추천 정보를 결합하여 최종 응답 반환
    project = repository.get_project(country.iso3)

    return AnalysisResponse(
        country=country_summary,
        analysis=AnalysisSummary(
            persona=request.persona,
            field=request.field,
            score=score,
            score_level=get_score_level(score),
        ),
        project_title=project.title,
        interpretation=project.summary,
        partner_types=project.partners,
        sdgs=project.sdgs,
        metrics=metrics,
        trend=trend,
        evidence=evidence,
        recommendations=repository.get_recommendations(country.iso3),
        risks=risks,
        gap_opportunity=country.gap_opportunity,
        capabilities=request.capabilities,
        data_status=DataStatus(
            completeness=(
                country.completeness
                if opportunity is None
                else round(opportunity.data_confidence)
            ),
            reference_date=(
                country.updated if opportunity is None else opportunity.as_of_date
            ),
            is_demo=opportunity is None or opportunity.is_demo,
            notice=(
                LIVE_DATA_NOTICE
                if opportunity is not None and not opportunity.is_demo
                else DATA_NOTICE
            ),
        ),
    )
