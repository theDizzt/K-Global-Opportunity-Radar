# 0. 테스트 모듈 불러오기
import tempfile
import unittest
from pathlib import Path

import httpx

from backend.collectors.mofa import MofaCollector, classify_field
from backend.database.connection import get_connection
from backend.models.analysis import AnalysisField
from backend.repositories.analysis_repository import AnalysisRepository
from backend.repositories.data_insight_repository import DataInsightRepository
from backend.services import data_insight_service


# 1. 외교부 SPARQL 수집·정제·SQLite 적재 검증
class MofaCollectorTestCase(unittest.TestCase):
    # 1.1. 실제 외부 호출 대신 고정 SPARQL 응답을 제공하는 임시 환경 구성
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "test.db"
        self.client = httpx.Client(transport=httpx.MockTransport(self._mock_response))

    # 1.1.1. 테스트용 HTTP 클라이언트와 임시 폴더 정리
    def tearDown(self):
        self.client.close()
        self.temp_directory.cleanup()

    # 1.2. 국가 매핑과 외교문서가 원본·정제 테이블에 저장되는지 검증
    def test_collects_country_alias_and_document(self):
        collector = MofaCollector(self.database_path, client=self.client)
        result = collector.collect(["VNM"], ("mofadaily",), limit=10)

        self.assertEqual(result.countries, 1)
        self.assertEqual(result.documents, 1)
        with get_connection(self.database_path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM raw_source_payloads").fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM country_aliases").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM document_countries").fetchone()[0], 1)

    # 1.3. 수집된 실제 문서가 시범 근거보다 우선 조회되는지 검증
    def test_live_document_is_used_as_analysis_evidence(self):
        collector = MofaCollector(self.database_path, client=self.client)
        collector.collect(["VNM"], ("mofadaily",), limit=10)

        evidence = AnalysisRepository(self.database_path).get_evidence("VNM", "교육")
        self.assertEqual(len(evidence), 1)
        self.assertFalse(evidence[0].is_demo)
        self.assertEqual(evidence[0].reference_date.isoformat(), "2023-03-22")
        self.assertIn("교육", evidence[0].category)

    # 1.4. 문서 내용의 분야 키워드 분류 검증
    def test_classifies_document_field(self):
        self.assertEqual(classify_field("디지털 교육과 교원 역량 강화"), "교육")
        self.assertEqual(classify_field("양국 외교장관 회담"), "외교 일반")

    # 1.5. 수집 문서의 품질 통계가 실제 적재값을 반영하는지 검증
    def test_builds_country_data_quality_report(self):
        collector = MofaCollector(self.database_path, client=self.client)
        collector.collect(["VNM"], ("mofadaily",), limit=10)
        original_repository = data_insight_service.data_insight_repository
        data_insight_service.data_insight_repository = DataInsightRepository(self.database_path)
        self.addCleanup(
            setattr,
            data_insight_service,
            "data_insight_repository",
            original_repository,
        )

        report = data_insight_service.build_country_quality("VNM")

        self.assertEqual(report.total_documents, 1)
        self.assertEqual(report.date_completeness, 100.0)
        self.assertEqual(report.fields, {"교육": 1})

    # 1.6. 원시지표가 산식 버전과 연도별 문서 가중치를 포함하는지 검증
    def test_builds_versioned_raw_signals(self):
        collector = MofaCollector(self.database_path, client=self.client)
        collector.collect(["VNM"], ("mofadaily",), limit=10)
        original_repository = data_insight_service.data_insight_repository
        data_insight_service.data_insight_repository = DataInsightRepository(self.database_path)
        self.addCleanup(
            setattr,
            data_insight_service,
            "data_insight_repository",
            original_repository,
        )

        result = data_insight_service.build_country_signals(
            "VNM",
            AnalysisField.EDUCATION,
        )

        self.assertEqual(result.formula_version, "mofa-raw-v1")
        self.assertEqual(len(result.points), 1)
        self.assertEqual(result.points[0].cooperation_signal, 1.5)
        self.assertEqual(result.points[0].policy_alignment, 100.0)

    # 1.7. 쿼리 종류에 따라 국가 매핑 또는 문서 응답 생성
    @staticmethod
    def _mock_response(request):
        query = request.url.params.get("query", "")
        if "hasISO_3CD" in query:
            bindings = [
                {
                    "country": {"type": "uri", "value": "http://opendata.mofa.go.kr/core/resource/Country/VN"},
                    "iso3": {"type": "literal", "value": "VNM"},
                    "iso2": {"type": "literal", "value": "VN"},
                    "label": {"type": "literal", "value": "베트남"},
                }
            ]
        else:
            bindings = [
                {
                    "country": {"type": "uri", "value": "http://opendata.mofa.go.kr/core/resource/Country/VN"},
                    "document": {"type": "uri", "value": "http://opendata.mofa.go.kr/mofadaily/resource/DiplomatJ/55021"},
                    "title": {"type": "literal", "value": "한·베트남 디지털 교육 협력 회담"},
                    "summary": {"type": "literal", "value": "교원 역량 강화와 대학 협력을 논의"},
                    "date": {"type": "literal", "value": '"20230322"^^xsd:integer'},
                    "year": {"type": "literal", "value": '"2023"^^xsd:integer'},
                }
            ]
        return httpx.Response(
            200,
            json={"head": {"vars": []}, "results": {"bindings": bindings}},
            request=request,
        )


# 2. 파일을 직접 실행했을 때 테스트 시작
if __name__ == "__main__":
    unittest.main()
