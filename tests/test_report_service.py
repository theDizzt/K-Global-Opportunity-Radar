"""근거 기반 보고서 서비스와 캐시 동작 테스트."""

import tempfile
import unittest
from pathlib import Path

from backend.database.connection import get_connection
from backend.database.init_db import initialize_database
from backend.models.analysis import AnalysisField, Persona
from backend.models.report import ReportRequest
from backend.repositories.analysis_repository import AnalysisRepository
from backend.repositories.country_repository import CountryRepository
from backend.repositories.report_repository import ReportRepository
from backend.services.report_service import build_report


class ReportServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "report.db"
        initialize_database(self.database_path, reset=True)
        self.analysis_repository = AnalysisRepository(self.database_path)
        self.country_repository = CountryRepository(self.database_path)
        self.report_repository = ReportRepository(self.database_path)
        self.request = ReportRequest(
            country_iso3="vnm",
            persona=Persona.STUDENT_TEAM,
            field=AnalysisField.EDUCATION,
            capabilities=["데이터 분석", "에듀테크"],
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_builds_rule_based_report_then_reuses_cache(self):
        country = self.country_repository.get_by_iso3("VNM")
        first = build_report(
            country,
            self.request,
            analysis_repo=self.analysis_repository,
            report_repo=self.report_repository,
        )
        second = build_report(
            country,
            self.request,
            analysis_repo=self.analysis_repository,
            report_repo=self.report_repository,
        )

        self.assertEqual(first.status, "fallback")
        self.assertEqual(first.generation_mode, "rule_based")
        self.assertEqual(second.status, "cached")
        self.assertEqual(first.request_hash, second.request_hash)
        self.assertEqual(self.report_repository.count(), 1)
        self.assertTrue(first.sources)
        self.assertTrue(all(source.source_url for source in first.sources))

    def test_blocks_generation_when_no_evidence_exists(self):
        with get_connection(self.database_path) as connection:
            connection.execute("DELETE FROM evidence WHERE country_iso3 = 'VNM'")

        country = self.country_repository.get_by_iso3("VNM")
        result = build_report(
            country,
            self.request,
            analysis_repo=self.analysis_repository,
            report_repo=self.report_repository,
        )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.generation_mode, "none")
        self.assertEqual(result.sources, [])
        self.assertEqual(self.report_repository.count(), 0)


if __name__ == "__main__":
    unittest.main()
