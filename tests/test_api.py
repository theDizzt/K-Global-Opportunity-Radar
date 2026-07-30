# 0. 테스트 모듈 불러오기
import os
import unittest

from httpx import ASGITransport, AsyncClient

# 테스트에서는 실제 OpenAI API를 호출하거나 비용을 발생시키지 않는다.
os.environ["OPENAI_REPORTS_ENABLED"] = "false"

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

    # 1.10. 실제 데이터 수집 상태 API의 기본 응답 구조 검증
    async def test_collection_status_contract(self):
        response = await self.client.get("/api/v1/collection/status")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["source_code"], "MOFA")
        self.assertIn("stored_documents", result)
        self.assertIn("datasets", result)

    # 1.11. 국가별 품질 보고서와 원시 신호 API의 입력 검증
    async def test_data_insight_contracts(self):
        quality = await self.client.get("/api/v1/countries/vnm/data-quality")
        signals = await self.client.get(
            "/api/v1/countries/VNM/signals",
            params={"field": "교육"},
        )
        missing_field = await self.client.get("/api/v1/countries/VNM/signals")

        self.assertEqual(quality.status_code, 200)
        self.assertEqual(quality.json()["country_iso3"], "VNM")
        self.assertEqual(signals.status_code, 200)
        self.assertEqual(signals.json()["formula_version"], "mofa-raw-v1")
        self.assertEqual(missing_field.status_code, 422)

    # 1.12. 근거 기반 초기 검토안과 SQLite 캐시 응답 검증
    async def test_report_contract_and_cache(self):
        request = {
            "country_iso3": "VNM",
            "persona": "대학생 팀",
            "field": "교육",
            "capabilities": ["데이터 분석", "에듀테크"],
        }
        first = await self.client.post("/api/v1/reports", json=request)
        second = await self.client.post("/api/v1/reports", json=request)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_result = first.json()
        second_result = second.json()
        self.assertIn(first_result["status"], {"fallback", "cached"})
        self.assertEqual(second_result["status"], "cached")
        self.assertEqual(first_result["generation_mode"], "rule_based")
        self.assertEqual(first_result["request_hash"], second_result["request_hash"])
        self.assertTrue(first_result["sources"])
        self.assertTrue(
            all(source["source_url"].startswith("https://") for source in first_result["sources"])
        )
        self.assertEqual(
            len({source["evidence_id"] for source in first_result["sources"]}),
            len(first_result["sources"]),
        )

    # 1.13. 지원하지 않는 국가의 보고서 요청은 404 반환
    async def test_report_unknown_country_returns_404(self):
        response = await self.client.post(
            "/api/v1/reports",
            json={
                "country_iso3": "USA",
                "persona": "대학생 팀",
                "field": "교육",
            },
        )
        self.assertEqual(response.status_code, 404)


# 2. 파일을 직접 실행했을 때 테스트 시작
if __name__ == "__main__":
    unittest.main()
