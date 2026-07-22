from fastapi import APIRouter, HTTPException, Query, status

from backend.models.country import CountryDetail, CountrySummary
from backend.repositories.country_repository import country_repository


router = APIRouter()


@router.get("", response_model=list[CountrySummary])
def list_countries(region: str | None = Query(default=None)):
    countries = country_repository.list_all(region=region)
    return [country.to_summary() for country in countries]


@router.get("/{iso3}", response_model=CountryDetail)
def get_country(iso3: str):
    country = country_repository.get_by_iso3(iso3)
    if country is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"지원하지 않는 국가 코드입니다: {iso3.upper()}",
        )
    return country.to_detail()
