from fastapi import APIRouter

from backend.models.analysis import AnalysisField, Persona
from backend.models.common import DataSourceItem, HealthResponse, OptionsResponse
from backend.repositories.analysis_repository import analysis_repository
from backend.repositories.country_repository import country_repository


router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(
        status="ok",
        data_source="sqlite",
        database_ready=country_repository.count() > 0,
    )


@router.get("/options", response_model=OptionsResponse)
def get_options():
    regions = sorted({country.region for country in country_repository.list_all()})
    return OptionsResponse(
        personas=[persona.value for persona in Persona],
        fields=[field.value for field in AnalysisField],
        regions=regions,
    )


@router.get("/sources", response_model=list[DataSourceItem])
def get_sources():
    return [DataSourceItem(**vars(source)) for source in analysis_repository.list_sources()]
