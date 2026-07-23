# 0. 테스트 모듈 불러오기
import tempfile
import unittest
from pathlib import Path

from backend.database.connection import get_connection
from backend.database.init_db import initialize_database
from backend.repositories.analysis_repository import AnalysisRepository
from backend.repositories.country_repository import CountryRepository


# 1. SQLite 스키마, 초기 데이터, 저장소 동작 검증
class DatabaseTestCase(unittest.TestCase):
    # 1.1. 각 테스트가 독립적으로 사용할 임시 데이터베이스 생성
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "test.db"
        initialize_database(self.database_path, reset=True)

    # 1.2. 테스트 종료 후 임시 데이터 정리
    def tearDown(self):
        self.temp_directory.cleanup()

    # 1.3. 테이블별 시범 데이터 적재 개수 검증
    def test_schema_and_seed_counts(self):
        with get_connection(self.database_path) as connection:
            counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "countries",
                    "country_indicators",
                    "signal_history",
                    "evidence",
                    "recommendations",
                    "risk_factors",
                    "data_sources",
                    "collection_logs",
                    "raw_source_payloads",
                    "country_aliases",
                    "source_documents",
                    "document_countries",
                )
            }

        self.assertEqual(counts["countries"], 3)
        self.assertEqual(counts["country_indicators"], 15)
        self.assertEqual(counts["signal_history"], 15)
        self.assertEqual(counts["evidence"], 9)
        self.assertEqual(counts["recommendations"], 9)
        self.assertEqual(counts["risk_factors"], 6)
        self.assertEqual(counts["data_sources"], 4)
        self.assertEqual(counts["collection_logs"], 4)
        self.assertEqual(counts["raw_source_payloads"], 0)
        self.assertEqual(counts["country_aliases"], 0)
        self.assertEqual(counts["source_documents"], 0)
        self.assertEqual(counts["document_countries"], 0)

    # 1.4. 데이터베이스 초기화를 반복해도 중복되지 않는지 검증
    def test_initialization_is_idempotent(self):
        initialize_database(self.database_path)
        repository = CountryRepository(self.database_path)
        self.assertEqual(repository.count(), 3)

    # 1.5. 국가와 분석 저장소의 정규화된 조회 결과 검증
    def test_repositories_read_normalized_data(self):
        countries = CountryRepository(self.database_path)
        analysis = AnalysisRepository(self.database_path)

        vietnam = countries.get_by_iso3("vnm")
        self.assertEqual(vietnam.country, "베트남")
        self.assertEqual(vietnam.diplomacy, 89)
        self.assertEqual(len(analysis.get_signal_history("VNM")), 5)
        self.assertEqual(len(analysis.get_evidence("VNM")), 3)
        self.assertEqual(len(analysis.get_recommendations("VNM")), 3)
        self.assertEqual(len(analysis.get_risks("VNM")), 2)


# 2. 파일을 직접 실행했을 때 테스트 시작
if __name__ == "__main__":
    unittest.main()
