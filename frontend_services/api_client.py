# 0. 모듈 불러오기
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from backend.models.analysis import AnalysisRequest
from backend.models.report import ReportRequest
from backend.repositories.analysis_repository import analysis_repository
from backend.repositories.country_repository import country_repository
from backend.services.analysis_service import build_analysis
from backend.services.report_service import build_report
from config.settings import (
    API_BASE_URL,
    API_FALLBACK_ENABLED,
    API_TIMEOUT,
    REPORT_API_TIMEOUT,
)


# 1. 프론트엔드가 사용한 데이터 전달 경로 구분
Transport = Literal["api", "sqlite_fallback"]


# 1.1. API와 SQLite 안전 모드를 모두 사용할 수 없을 때 발생하는 오류
class ApiClientError(RuntimeError):
    """API와 설정된 안전 모드를 모두 사용할 수 없을 때 발생하는 오류입니다."""


# 2. API 응답 데이터와 실제 전달 경로를 함께 보관
@dataclass(frozen=True)
class GatewayResult:
    payload: Any
    transport: Transport


# 3. Streamlit과 FastAPI 사이의 데이터 요청 처리
class RadarGateway:
    # 3.1. API 주소, 제한 시간, SQLite 안전 모드 설정
    def __init__(
        self,
        base_url: str = API_BASE_URL,
        timeout: float = API_TIMEOUT,
        report_timeout: float = REPORT_API_TIMEOUT,
        fallback_enabled: bool = API_FALLBACK_ENABLED,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.report_timeout = report_timeout
        self.fallback_enabled = fallback_enabled

    # 3.2. 화면 선택 항목 조회
    def get_options(self):
        return self._request("GET", "/options", self._fallback_options)

    # 3.3. 국가 목록 조회
    def get_countries(self):
        return self._request("GET", "/countries", self._fallback_countries)

    # 3.4. 공공데이터 출처 목록 조회
    def get_sources(self):
        return self._request("GET", "/sources", self._fallback_sources)

    # 3.5. 국가·사용자·분야별 분석 요청
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

    # 3.6. 근거 기반 AI 초기 사업 검토안 생성 요청
    def generate_report(
        self,
        country_iso3: str,
        persona: str,
        field: str,
        capabilities=None,
    ):
        body = {
            "country_iso3": country_iso3,
            "persona": persona,
            "field": field,
            "capabilities": list(capabilities or []),
        }
        return self._request(
            "POST",
            "/reports",
            lambda: self._fallback_report(body),
            request_timeout=self.report_timeout,
            json=body,
        )

    # 3.7. HTTP 요청 실행 및 실패 시 SQLite 안전 모드 전환
    def _request(self, method: str, path: str, fallback, **kwargs):
        request_timeout = kwargs.pop("request_timeout", self.timeout)
        try:
            with httpx.Client(base_url=self.base_url, timeout=request_timeout) as client:
                response = client.request(method, path, **kwargs)
                response.raise_for_status()
                return GatewayResult(response.json(), "api")
        except (httpx.HTTPError, ValueError) as error:
            if self.fallback_enabled:
                return GatewayResult(fallback(), "sqlite_fallback")
            raise ApiClientError(f"Backend API request failed: {method} {path}") from error

    # 4. API 장애 시 SQLite 저장소에서 동일한 응답 생성
    # 4.1. SQLite의 사용자 유형·분야·권역을 선택 항목 형식으로 변환
    @staticmethod
    def _fallback_options():
        from backend.models.analysis import AnalysisField, Persona

        countries = country_repository.list_all()
        return {
            "personas": [item.value for item in Persona],
            "fields": [item.value for item in AnalysisField],
            "regions": sorted({country.region for country in countries}),
        }

    # 4.2. SQLite 국가 레코드를 API 국가 목록 형식으로 변환
    @staticmethod
    def _fallback_countries():
        return [
            country.to_summary().model_dump(mode="json")
            for country in country_repository.list_all()
        ]

    # 4.3. SQLite 제공기관 레코드를 API 출처 목록 형식으로 변환
    @staticmethod
    def _fallback_sources():
        return [vars(source) for source in analysis_repository.list_sources()]

    # 4.4. SQLite 국가정보와 요청 조건으로 분석 응답 생성
    @staticmethod
    def _fallback_analysis(body):
        request = AnalysisRequest(**body)
        country = country_repository.get_by_iso3(request.country_iso3)
        if country is None:
            raise ApiClientError(f"Country not found: {request.country_iso3}")
        return build_analysis(country, request).model_dump(mode="json")

    # 4.5. 백엔드 장애 시 같은 SQLite와 RAG 서비스를 직접 호출
    @staticmethod
    def _fallback_report(body):
        request = ReportRequest(**body)
        country = country_repository.get_by_iso3(request.country_iso3)
        if country is None:
            raise ApiClientError(f"Country not found: {request.country_iso3}")
        return build_report(country, request).model_dump(mode="json")


# 5. 화면 전역에서 재사용하는 API 게이트웨이 인스턴스
radar_gateway = RadarGateway()
