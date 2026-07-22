import unittest

from httpx import ASGITransport, AsyncClient

from backend.main import app


class ApiTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_health_check(self):
        response = await self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["data_source"], "sqlite")
        self.assertTrue(response.json()["database_ready"])

    async def test_country_list_contains_three_demo_countries(self):
        response = await self.client.get("/api/v1/countries")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 3)

    async def test_country_detail_normalizes_iso3(self):
        response = await self.client.get("/api/v1/countries/vnm")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["iso3"], "VNM")

    async def test_unknown_country_returns_404(self):
        response = await self.client.get("/api/v1/countries/USA")
        self.assertEqual(response.status_code, 404)

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

    async def test_sources_expose_original_links(self):
        response = await self.client.get("/api/v1/sources")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 4)
        self.assertTrue(all(source["url"].startswith("https://") for source in response.json()))

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


if __name__ == "__main__":
    unittest.main()
