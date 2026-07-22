import unittest

from frontend_services.api_client import RadarGateway


class FrontendGatewayTestCase(unittest.TestCase):
    def setUp(self):
        self.gateway = RadarGateway(
            base_url="http://127.0.0.1:9/api/v1",
            timeout=0.05,
            fallback_enabled=True,
        )

    def test_sqlite_fallback_returns_country_options_and_sources(self):
        countries = self.gateway.get_countries()
        options = self.gateway.get_options()
        sources = self.gateway.get_sources()

        self.assertEqual(countries.transport, "sqlite_fallback")
        self.assertEqual(len(countries.payload), 3)
        self.assertIn("교육", options.payload["fields"])
        self.assertEqual(len(sources.payload), 4)

    def test_sqlite_fallback_analysis_matches_api_contract(self):
        result = self.gateway.analyze("VNM", "대학생 팀", "교육")

        self.assertEqual(result.transport, "sqlite_fallback")
        self.assertEqual(result.payload["country"]["iso3"], "VNM")
        self.assertEqual(len(result.payload["metrics"]), 4)
        self.assertTrue(result.payload["interpretation"])


if __name__ == "__main__":
    unittest.main()
