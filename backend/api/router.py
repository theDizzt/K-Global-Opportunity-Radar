# 0. 모듈 불러오기
from fastapi import APIRouter

from backend.api.routes import analysis, countries, data_insights, meta, reports


# 1. 기능별 API 라우터를 하나의 버전 라우터로 통합
api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(countries.router, prefix="/countries", tags=["countries"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(data_insights.router)
