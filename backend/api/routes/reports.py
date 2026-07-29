"""근거 기반 초기 사업 검토안 API."""

from fastapi import APIRouter, HTTPException, status

from backend.models.report import ReportRequest, ReportResponse
from backend.repositories.analysis_repository import analysis_repository
from backend.repositories.country_repository import country_repository
from backend.repositories.report_repository import report_repository
from backend.services.report_service import build_report


router = APIRouter()


@router.post("", response_model=ReportResponse)
def create_report(request: ReportRequest):
    country = country_repository.get_by_iso3(request.country_iso3)
    if country is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"지원하지 않는 국가 코드입니다: {request.country_iso3}",
        )
    return build_report(
        country,
        request,
        analysis_repo=analysis_repository,
        report_repo=report_repository,
    )
