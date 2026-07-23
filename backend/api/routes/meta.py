# 0. 모듈 불러오기
from fastapi import APIRouter

from backend.models.analysis import AnalysisField, Persona
from backend.models.common import DataSourceItem, HealthResponse, OptionsResponse
from backend.repositories.analysis_repository import analysis_repository
from backend.repositories.country_repository import country_repository


# 1. 서버 상태와 공통 선택 항목을 제공하는 라우터
router = APIRouter(tags=["meta"])


# 1.1. API와 SQLite 데이터베이스 준비 상태 확인
@router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(
        status="ok",
        data_source="sqlite",
        database_ready=country_repository.count() > 0,
    )


# 1.2. 사용자 유형, 분석 분야, 권역 목록 조회
@router.get("/options", response_model=OptionsResponse)
def get_options():
    regions = sorted({country.region for country in country_repository.list_all()})
    return OptionsResponse(
        personas=[persona.value for persona in Persona],
        fields=[field.value for field in AnalysisField],
        regions=regions,
    )


# 1.3. 분석에 사용하는 공공데이터 출처 조회
@router.get("/sources", response_model=list[DataSourceItem])
def get_sources():
    return [DataSourceItem(**vars(source)) for source in analysis_repository.list_sources()]
