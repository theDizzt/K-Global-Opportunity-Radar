# 0. 모듈 불러오기
from fastapi import APIRouter, HTTPException, Query, status

from backend.models.analysis import AnalysisField
from backend.models.data_insight import (
    CollectionStatusResponse,
    CountryDataQualityResponse,
    CountrySignalsResponse,
    SourceDocumentItem,
)
from backend.repositories.country_repository import country_repository
from backend.services.data_insight_service import (
    build_collection_status,
    build_country_quality,
    build_country_signals,
    build_source_documents,
)


# 1. 실제 수집 데이터의 상태·품질·원시지표 조회 라우터
router = APIRouter(tags=["data-insights"])


# 1.1. 외교부 데이터의 최근 수집 상태와 적재량 조회
@router.get("/collection/status", response_model=CollectionStatusResponse)
def get_collection_status():
    return build_collection_status()


# 1.2. 국가별 누락·분류·공유 문서 품질 보고서 조회
@router.get(
    "/countries/{iso3}/data-quality",
    response_model=CountryDataQualityResponse,
)
def get_country_data_quality(iso3: str):
    normalized_iso3 = _validate_country(iso3)
    return build_country_quality(normalized_iso3)


# 1.3. 국가와 선택 분야에 해당하는 최신 원문 근거 목록 조회
@router.get("/countries/{iso3}/evidence", response_model=list[SourceDocumentItem])
def get_country_evidence(
    iso3: str,
    field: AnalysisField | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    normalized_iso3 = _validate_country(iso3)
    return build_source_documents(
        normalized_iso3,
        field.value if field is not None else None,
        limit,
    )


# 1.4. 국가·분야별 연도 단위 협력 신호와 정책 정합성 원시지표 조회
@router.get("/countries/{iso3}/signals", response_model=CountrySignalsResponse)
def get_country_signals(iso3: str, field: AnalysisField = Query(...)):
    normalized_iso3 = _validate_country(iso3)
    return build_country_signals(normalized_iso3, field)


# 2. ISO3 코드를 정규화하고 지원 국가인지 확인
def _validate_country(iso3: str):
    normalized_iso3 = iso3.strip().upper()
    if country_repository.get_by_iso3(normalized_iso3) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"지원하지 않는 국가 코드입니다: {normalized_iso3}",
        )
    return normalized_iso3
