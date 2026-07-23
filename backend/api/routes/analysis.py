# 0. 모듈 불러오기
from fastapi import APIRouter, HTTPException, status

from backend.models.analysis import AnalysisRequest, AnalysisResponse
from backend.repositories.country_repository import country_repository
from backend.services.analysis_service import build_analysis


# 1. 국가별 협력기회 분석 라우터
router = APIRouter()


# 1.1. 요청 조건을 검증하고 종합 분석 결과 반환
@router.post("", response_model=AnalysisResponse)
def analyze_country(request: AnalysisRequest):
    country = country_repository.get_by_iso3(request.country_iso3)
    if country is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"지원하지 않는 국가 코드입니다: {request.country_iso3.upper()}",
        )
    return build_analysis(country, request)
