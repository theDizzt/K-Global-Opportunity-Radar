# 0. 테스트 모듈 불러오기
import unittest

from httpx import ASGITransport, AsyncClient

from backend.main import app


# 1. FastAPI 엔드포인트와 응답 계약 검증
class ApiTestCase(unittest.IsolatedAsyncioTestCase):
    # 1.1. 각 테스트에서 사용할 비동기 API 클라이언트 준비
    async def asyncSetUp(self):
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        )

    # 1.2. 테스트 종료 후 비동기 클라이언트 정리
    async def asyncTearDown(self):
        await self.client.aclose()

    # 1.3. 상태 확인 API 검증
    async def test_health_check(self):
        response = await self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["data_source"], "sqlite")
        self.assertTrue(response.json()["database_ready"])

    # 1.4. 시범 국가 목록 API 검증
    async def test_country_list_contains_three_demo_countries(self):
        response = await self.client.get("/api/v1/countries")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 3)

    # 1.5. ISO3 소문자 입력의 대문자 정규화 검증
    async def test_country_detail_normalizes_iso3(self):
        response = await self.client.get("/api/v1/countries/vnm")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["iso3"], "VNM")

    # 1.6. 지원하지 않는 국가의 404 응답 검증
    async def test_unknown_country_returns_404(self):
        response = await self.client.get("/api/v1/countries/USA")
        self.assertEqual(response.status_code, 404)

    # 1.7. 분석 API의 핵심 응답 구조 검증
    async def test_analysis_contract(self):
        response = await self.client.post(
            "/api/v1/analysis",
            json={
                "country_iso3": "VNM",
                "persona": "대학생 팀",
                "field": "교육",
                "capabilities": ["데이터 분석", "에듀테크"],
            },
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["country"]["iso3"], "VNM")
        self.assertEqual(len(result["metrics"]), 4)
        self.assertEqual(len(result["trend"]), 5)
        self.assertTrue(result["data_status"]["is_demo"])
        self.assertTrue(all(item["source_url"] for item in result["evidence"]))
        self.assertTrue(result["interpretation"])
        self.assertTrue(result["partner_types"])
        self.assertTrue(result["sdgs"])

    # 1.8. 공공데이터 출처와 원문 URL 응답 검증
    async def test_sources_expose_original_links(self):
        response = await self.client.get("/api/v1/sources")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 4)
        self.assertTrue(all(source["url"].startswith("https://") for source in response.json()))

    # 1.9. 지원하지 않는 분석 분야의 입력 검증
    async def test_invalid_analysis_field_returns_422(self):
        response = await self.client.post(
            "/api/v1/analysis",
            json={
                "country_iso3": "VNM",
                "persona": "대학생 팀",
                "field": "우주개발",
            },
        )
        self.assertEqual(response.status_code, 422)


# 2. 파일을 직접 실행했을 때 테스트 시작
if __name__ == "__main__":
    unittest.main()
