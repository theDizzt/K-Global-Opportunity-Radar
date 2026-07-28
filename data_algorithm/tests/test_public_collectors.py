from __future__ import annotations

import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.kf_pipeline import KfCollector
from opportunity_radar.kf_eschool import KfESchoolCollector
from opportunity_radar.mofa_lod import MofaLodCollector
from opportunity_radar.mofa_pipeline import MofaCollector


def api_response(items: list[dict]) -> bytes:
    return json.dumps(
        {
            "response": {
                "header": {"resultCode": "0", "resultMsg": "OK"},
                "body": {
                    "items": {"item": items}, "numOfRows": 200,
                    "pageNo": 1, "totalCount": len(items),
                },
            }
        },
        ensure_ascii=False,
    ).encode()


class PublicCollectorsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = connect(Path(self.tmp.name) / "public.db")
        initialize(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_kf_collects_business_org_and_results(self):
        def transport(url: str) -> bytes:
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query)
            iso2 = query.get("cond[country_iso_alp2::EQ]", [""])[0]
            country = {"VN": "Vietnam", "ID": "Indonesia", "MN": "Mongolia"}[iso2]
            common = {"country_iso_alp2": iso2, "country_eng_nm": country}
            if "BusinessInfoService" in parsed.path:
                return api_response([{**common, "business_year": 2025,
                    "kor_business_nm": f"{country} 한국어 교육", "business_purpose": "교육 협력",
                    "unit_business": "한국학", "detail_business": "교원 지원"}])
            if "PublicDiplomacyOrgService" in parsed.path:
                return api_response([{**common, "kor_org_nm": f"{country} University", "benefit_cnt": 2}])
            return api_response([{**common, "business_year": 2025,
                "kor_business_nm": f"{country} 한국어 교육 실적", "org_nm": f"{country} University",
                "business_degree": 1}])

        counts = KfCollector(self.conn, "test-key", transport=transport).collect(page_size=200)

        self.assertEqual(counts, {"VNM": 3, "IDN": 3, "MNG": 3})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM kf_partner_org").fetchone()[0], 3)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM evidence WHERE sector_code='education'").fetchone()[0], 6)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM raw_api_response WHERE source_type='KF'").fetchone()[0], 9)

    def test_kf_eschool_collects_target_country_courses(self):
        html = """
        <html><body><table class="list">
          <tbody id="globalEschoolList">
            <tr>
              <td>2024</td><td>국내-해외 연계형</td><td>서울대학교</td>
              <td>한국학</td><td>한국경제</td><td>가을</td>
              <td>베트남</td><td>하노이대학교</td><td>59</td>
            </tr>
            <tr>
              <td>2024</td><td>VOD</td><td>한국외국어대학교</td>
              <td>한국어</td><td>한국어 1</td><td>봄</td>
              <td>인도네시아</td><td>인도네시아대학교</td><td>31</td>
            </tr>
            <tr>
              <td>2024</td><td>실시간</td><td>서울대학교</td>
              <td>한국학</td><td>한국사회</td><td>겨울</td>
              <td>독일</td><td>튀빙겐대학교</td><td>20</td>
            </tr>
          </tbody>
        </table></body></html>
        """.encode("utf-8")

        counts = KfESchoolCollector(
            self.conn,
            transport=lambda _url: html,
        ).collect()

        self.assertEqual(counts, {"VNM": 1, "IDN": 1, "MNG": 0})
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM kf_eschool_course").fetchone()[0],
            2,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM evidence WHERE sector_code='korean_studies'"
            ).fetchone()[0],
            2,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM raw_api_response WHERE source_type='KF_ESCHOOL'"
            ).fetchone()[0],
            1,
        )

    def test_mofa_collects_profiles_and_travel_warning(self):
        def transport(url: str) -> bytes:
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query)
            if "TravelWarning" in parsed.path:
                return api_response([
                    {"id": "1", "iso_code": "VNM", "country_name": "베트남", "attention": "여행유의"},
                    {"id": "2", "iso_code": "IDN", "country_name": "인도네시아", "limita": "여행자제"},
                    {"id": "3", "iso_code": "MNG", "country_name": "몽골"},
                    {"id": "4", "iso_code": "NPL", "country_name": "네팔", "control": "출국권고"},
                ])
            iso2 = query["cond[country_iso_alp2::EQ]"][0]
            common = {"country_iso_alp2": iso2, "country_nm": iso2}
            if "OverviewEconomic" in parsed.path:
                return api_response([{**common, "gdp": "1000", "gdp_per_capita": "200",
                    "gdp_growth_rate": "5.5", "export_amount": "300", "import_amount": "250"}])
            return api_response([{**common, "diplomatic_relations": "교육 협력 협정",
                "export_amount": "300", "import_amount": "250"}])

        counts = MofaCollector(self.conn, "test-key", transport=transport).collect(page_size=200)

        self.assertEqual(counts, {"VNM": 3, "IDN": 3, "MNG": 3})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM country_profile").fetchone()[0], 6)
        levels = dict(self.conn.execute("SELECT country_iso3, warning_level FROM safety_notice"))
        self.assertEqual(levels, {"VNM": 1, "IDN": 2, "MNG": 0})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM evidence WHERE sector_code='education'").fetchone()[0], 3)

    def test_lod_collects_document_literals_and_uri(self):
        def transport(url: str) -> bytes:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["query"][0]
            if "Vietnam" not in query:
                bindings = []
            else:
                subject = "http://opendata.mofa.go.kr/mofapress/resource/Press/1"
                bindings = [
                    {"s": {"value": subject}, "p": {"value": "http://www.w3.org/2000/01/rdf-schema#label"},
                     "o": {"value": "Vietnam digital education cooperation"}},
                    {"s": {"value": subject}, "p": {"value": "http://purl.org/dc/terms/date"},
                     "o": {"value": "2025"}},
                ]
            return json.dumps({"head": {"vars": ["s", "p", "o"]},
                               "results": {"bindings": bindings}}).encode()

        collector = MofaLodCollector(
            self.conn, transport=transport,
            datasets={"mofapress": "http://example.test/mofapress/sparql"},
        )
        counts = collector.collect(page_size=10, max_pages=1)

        self.assertEqual(counts, {"VNM": 1, "IDN": 0, "MNG": 0})
        row = self.conn.execute("SELECT source_url, published_at FROM source_record WHERE source_type='LOD'").fetchone()
        self.assertEqual(row["source_url"], "http://opendata.mofa.go.kr/mofapress/resource/Press/1")
        self.assertEqual(row["published_at"], "2025-01-01")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM evidence WHERE sector_code='education'").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
