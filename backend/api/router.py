from fastapi import APIRouter

from backend.api.routes import analysis, countries, meta


api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(countries.router, prefix="/countries", tags=["countries"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
