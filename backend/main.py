"""FastAPI application entry point."""

from fastapi import FastAPI

from backend.api.router import api_router


app = FastAPI(
    title="K-Global Opportunity Radar API",
    version="0.1.0",
    description=(
        "외교 공공데이터 기반 국가 정보와 협력기회 분석 결과를 제공하는 "
        "MVP 백엔드 API"
    ),
)
app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def read_root():
    return {
        "service": "K-Global Opportunity Radar API",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
