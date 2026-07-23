import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from backend.database.connection import get_connection
from backend.database.init_db import initialize_database
from backend.main import app
from backend.models.analysis import AnalysisField, AnalysisRequest, Persona
from backend.repositories.analysis_repository import AnalysisRepository
from backend.repositories.country_repository import CountryRepository
from backend.services.analysis_service import build_analysis


class AlgorithmBackendIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "backend.db"
        initialize_database(self.database_path)
        with get_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO opportunity_scores (
                    country_iso3, field, score_version, as_of_date,
                    demand_score, policy_alignment_score, readiness_score,
                    korean_base_score, opportunity_score, data_confidence,
                    risk_level, sensitivity_low, sensitivity_high
                ) VALUES (
                    'VNM', '교육', 'v-test', '2026-07-23',
                    80, 70, 60, 50, 68, 90, 1, 65, 71
                )
                """
            )
        self.analysis_repository = AnalysisRepository(self.database_path)
        self.country_repository = CountryRepository(self.database_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_analysis_prefers_synced_score_over_demo_formula(self):
        country = self.country_repository.get_by_iso3("VNM")
        request = AnalysisRequest(
            country_iso3="VNM",
            persona=Persona.STARTUP,
            field=AnalysisField.EDUCATION,
        )
        with patch(
            "backend.services.analysis_service.analysis_repository",
            self.analysis_repository,
        ):
            response = build_analysis(country, request)

        self.assertEqual(response.analysis.score, 68.0)
        self.assertFalse(response.data_status.is_demo)
        self.assertEqual(response.data_status.completeness, 90)
        self.assertEqual(response.country.data_completeness, 90)
        self.assertEqual(
            {metric.code: metric.score for metric in response.metrics},
            {
                "demand": 80,
                "policy_alignment": 70,
                "korean_base": 50,
                "readiness": 60,
            },
        )
        self.assertEqual(response.trend[-1].year, 2026)
        self.assertEqual(response.trend[-1].score, 68)

    def test_analysis_keeps_demo_fallback_when_score_is_missing(self):
        country = self.country_repository.get_by_iso3("IDN")
        request = AnalysisRequest(
            country_iso3="IDN",
            persona=Persona.STARTUP,
            field=AnalysisField.EDUCATION,
        )
        with patch(
            "backend.services.analysis_service.analysis_repository",
            self.analysis_repository,
        ):
            response = build_analysis(country, request)

        self.assertTrue(response.data_status.is_demo)
        self.assertEqual(len(response.metrics), 4)


    def test_analysis_api_returns_synced_score(self):
        async def request_analysis():
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.post(
                    "/api/v1/analysis",
                    json={
                        "country_iso3": "VNM",
                        "persona": "스타트업",
                        "field": "교육",
                        "capabilities": ["데이터 분석"],
                    },
                )

        with (
            patch(
                "backend.api.routes.analysis.country_repository",
                self.country_repository,
            ),
            patch(
                "backend.services.analysis_service.analysis_repository",
                self.analysis_repository,
            ),
        ):
            response = asyncio.run(request_analysis())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["analysis"]["score"], 68.0)
        self.assertFalse(payload["data_status"]["is_demo"])
        self.assertEqual(payload["data_status"]["completeness"], 90)
        self.assertEqual(
            {metric["code"]: metric["score"] for metric in payload["metrics"]},
            {
                "demand": 80,
                "policy_alignment": 70,
                "korean_base": 50,
                "readiness": 60,
            },
        )
if __name__ == "__main__":
    unittest.main()
