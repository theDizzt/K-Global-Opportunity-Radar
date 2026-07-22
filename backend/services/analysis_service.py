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
from services.scoring_service import calculate_score, get_analysis_metrics, get_score_level


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

# 3. 국가정보와 사용자 요청을 결합하여 전체 분석 응답 생성
def build_analysis(country: CountryRecord, request: AnalysisRequest):
    # 3.1. 사용자 유형과 분야에 따른 종합점수·세부지표 계산
    persona = request.persona.value
    field = request.field.value
    score = calculate_score(country, persona, field)

    metrics = [
        Metric(code=METRIC_CODES[name], name=name, score=value)
        for name, value, _, _ in get_analysis_metrics(country, field)
    ]
    # 3.2. 저장된 연도별 추세의 최신값을 현재 종합점수로 갱신
    history = analysis_repository.get_signal_history(country.iso3)
    trend_values = [value for _, value in history]
    if trend_values:
        trend_values[-1] = round(score)
    trend = [
        TrendPoint(year=year, score=value)
        for (year, _), value in zip(history, trend_values, strict=True)
    ]
    # 3.3. 저장소의 근거와 주의 요인을 API 응답 모델로 변환
    evidence = [
        EvidenceItem(
            title=item.title,
            category=item.category,
            source=item.source,
            reference_date=item.reference_date,
            source_url=item.source_url,
            is_demo=item.is_demo,
        )
        for item in analysis_repository.get_evidence(country.iso3)
    ]
    risks = [
        RiskItem(
            title=item.title,
            level=item.level,
            score=item.score,
            source=item.source,
            source_url=item.source_url,
        )
        for item in analysis_repository.get_risks(country.iso3)
    ]
    # 3.4. 프로젝트와 추천 정보를 결합하여 최종 응답 반환
    project = analysis_repository.get_project(country.iso3)

    return AnalysisResponse(
        country=country.to_summary(),
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
        recommendations=analysis_repository.get_recommendations(country.iso3),
        risks=risks,
        gap_opportunity=country.gap_opportunity,
        capabilities=request.capabilities,
        data_status=DataStatus(
            completeness=country.completeness,
            reference_date=country.updated,
            is_demo=True,
            notice=DATA_NOTICE,
        ),
    )
