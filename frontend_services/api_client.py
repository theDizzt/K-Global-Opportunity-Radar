from dataclasses import dataclass
from typing import Any, Literal

import httpx

from backend.models.analysis import AnalysisRequest
from backend.repositories.analysis_repository import analysis_repository
from backend.repositories.country_repository import country_repository
from backend.services.analysis_service import build_analysis
from config.settings import API_BASE_URL, API_FALLBACK_ENABLED, API_TIMEOUT


Transport = Literal["api", "sqlite_fallback"]


class ApiClientError(RuntimeError):
    """Raised when neither the API nor the configured fallback is available."""


@dataclass(frozen=True)
class GatewayResult:
    payload: Any
    transport: Transport


class RadarGateway:
    def __init__(
        self,
        base_url: str = API_BASE_URL,
        timeout: float = API_TIMEOUT,
        fallback_enabled: bool = API_FALLBACK_ENABLED,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.fallback_enabled = fallback_enabled

    def get_options(self):
        return self._request("GET", "/options", self._fallback_options)

    def get_countries(self):
        return self._request("GET", "/countries", self._fallback_countries)

    def get_sources(self):
        return self._request("GET", "/sources", self._fallback_sources)

    def analyze(self, country_iso3: str, persona: str, field: str, capabilities=None):
        body = {
            "country_iso3": country_iso3,
            "persona": persona,
            "field": field,
            "capabilities": list(capabilities or []),
        }
        return self._request(
            "POST",
            "/analysis",
            lambda: self._fallback_analysis(body),
            json=body,
        )

    def _request(self, method: str, path: str, fallback, **kwargs):
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                response = client.request(method, path, **kwargs)
                response.raise_for_status()
                return GatewayResult(response.json(), "api")
        except (httpx.HTTPError, ValueError) as error:
            if self.fallback_enabled:
                return GatewayResult(fallback(), "sqlite_fallback")
            raise ApiClientError(f"Backend API request failed: {method} {path}") from error

    @staticmethod
    def _fallback_options():
        from backend.models.analysis import AnalysisField, Persona

        countries = country_repository.list_all()
        return {
            "personas": [item.value for item in Persona],
            "fields": [item.value for item in AnalysisField],
            "regions": sorted({country.region for country in countries}),
        }

    @staticmethod
    def _fallback_countries():
        return [
            country.to_summary().model_dump(mode="json")
            for country in country_repository.list_all()
        ]

    @staticmethod
    def _fallback_sources():
        return [vars(source) for source in analysis_repository.list_sources()]

    @staticmethod
    def _fallback_analysis(body):
        request = AnalysisRequest(**body)
        country = country_repository.get_by_iso3(request.country_iso3)
        if country is None:
            raise ApiClientError(f"Country not found: {request.country_iso3}")
        return build_analysis(country, request).model_dump(mode="json")


radar_gateway = RadarGateway()
