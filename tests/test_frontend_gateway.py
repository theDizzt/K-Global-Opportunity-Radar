# 0. 테스트 모듈 불러오기
import unittest

from frontend_services.api_client import RadarGateway


# 1. API 장애 시 프론트엔드 SQLite 안전 모드 검증
class FrontendGatewayTestCase(unittest.TestCase):
    # 1.1. 연결할 수 없는 API 주소로 안전 모드 환경 구성
    def setUp(self):
        self.gateway = RadarGateway(
            base_url="http://127.0.0.1:9/api/v1",
            timeout=0.05,
            fallback_enabled=True,
        )

    # 1.2. 국가·선택 항목·출처 조회의 SQLite 전환 검증
    def test_sqlite_fallback_returns_country_options_and_sources(self):
        countries = self.gateway.get_countries()
        options = self.gateway.get_options()
        sources = self.gateway.get_sources()

        self.assertEqual(countries.transport, "sqlite_fallback")
        self.assertEqual(len(countries.payload), 3)
        self.assertIn("교육", options.payload["fields"])
        self.assertEqual(len(sources.payload), 4)

    # 1.3. 안전 모드 분석 결과가 API 계약과 동일한지 검증
    def test_sqlite_fallback_analysis_matches_api_contract(self):
        result = self.gateway.analyze("VNM", "대학생 팀", "교육")

        self.assertEqual(result.transport, "sqlite_fallback")
        self.assertEqual(result.payload["country"]["iso3"], "VNM")
        self.assertEqual(len(result.payload["metrics"]), 4)
        self.assertTrue(result.payload["interpretation"])


# 2. 파일을 직접 실행했을 때 테스트 시작
if __name__ == "__main__":
    unittest.main()
