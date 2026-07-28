from __future__ import annotations

import tempfile
import urllib.error
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, patch

from opportunity_radar.db import connect, initialize
from opportunity_radar.koica_pipeline import KoicaCollector
from opportunity_radar.resilient_koica import ResilientKoicaCollector


LIST_XML = b"""<?xml version='1.0' encoding='UTF-8'?>
<response><HEADER><RESULT_CODE>00</RESULT_CODE><RESULT_MSG>OK</RESULT_MSG></HEADER><BODY>
<ITEMS>
<ITEM><BSNS_NO>VN-1</BSNS_NO><BSNS_NM>Digital education</BSNS_NM><NATION_NM>Vietnam</NATION_NM><NATION_CD>VN</NATION_CD><BSNS_BEGIN_YEAR>2024</BSNS_BEGIN_YEAR><BSNS_END_YEAR>2027</BSNS_END_YEAR><BSNS_TY_CD>0102</BSNS_TY_CD><SPORT_REALM_CD>EDU</SPORT_REALM_CD><SPORT_REALM_NM>Education</SPORT_REALM_NM><KOICA_AREA_SE_CD>AS</KOICA_AREA_SE_CD><KOICA_AREA_SE_NM>Asia</KOICA_AREA_SE_NM><TOT_CNT>3</TOT_CNT></ITEM>
<ITEM><BSNS_NO>ID-1</BSNS_NO><BSNS_NM>Health system</BSNS_NM><NATION_NM>Indonesia</NATION_NM><NATION_CD>ID</NATION_CD><BSNS_BEGIN_YEAR>2023</BSNS_BEGIN_YEAR><BSNS_END_YEAR>2026</BSNS_END_YEAR><BSNS_TY_CD>0102</BSNS_TY_CD><SPORT_REALM_CD>HEA</SPORT_REALM_CD><SPORT_REALM_NM>Health</SPORT_REALM_NM><KOICA_AREA_SE_CD>AS</KOICA_AREA_SE_CD><KOICA_AREA_SE_NM>Asia</KOICA_AREA_SE_NM><TOT_CNT>3</TOT_CNT></ITEM>
<ITEM><BSNS_NO>MN-1</BSNS_NO><BSNS_NM>Vocational training</BSNS_NM><NATION_NM></NATION_NM><NATION_CD>1514</NATION_CD><BSNS_BEGIN_YEAR>2025</BSNS_BEGIN_YEAR><BSNS_END_YEAR>2027</BSNS_END_YEAR><BSNS_TY_CD>0102</BSNS_TY_CD><SPORT_REALM_CD>EDU</SPORT_REALM_CD><SPORT_REALM_NM>Education</SPORT_REALM_NM><KOICA_AREA_SE_CD>AS</KOICA_AREA_SE_CD><KOICA_AREA_SE_NM>Asia</KOICA_AREA_SE_NM><TOT_CNT>4</TOT_CNT></ITEM>
<ITEM><BSNS_NO>NP-1</BSNS_NO><BSNS_NM>Agriculture</BSNS_NM><NATION_NM>Nepal</NATION_NM><TOT_CNT>3</TOT_CNT></ITEM>
</ITEMS><TOTAL_COUNT>4</TOTAL_COUNT></BODY></response>"""


def detail_xml(number: str) -> bytes:
    country = {
        "VN-1": "Vietnam",
        "ID-1": "Indonesia",
        "MN-1": "Mongolia",
    }[number]
    return f"""<?xml version='1.0' encoding='UTF-8'?>
    <response><HEADER><RESULT_CODE>00</RESULT_CODE></HEADER><BODY><ITEM>
    <BSNS_NO>{number}</BSNS_NO><KOREAN_BSNS_NM>{number} project</KOREAN_BSNS_NM>
    <BSNS_BUDGET_DOLLAR_AMOUNT>1000000</BSNS_BUDGET_DOLLAR_AMOUNT>
    <BSNS_CN_KOREAN_DC>교육 및 보건 사업 내용</BSNS_CN_KOREAN_DC>
    <BSNS_PURPS_KOREAN_DC>역량강화</BSNS_PURPS_KOREAN_DC>
    <RECIPCONTY_NM>{country}</RECIPCONTY_NM><REOF_NM>Partner Ministry</REOF_NM>
    </ITEM><PRTN_STTUS_LIST><PRTN_STTUS>진행</PRTN_STTUS></PRTN_STTUS_LIST></BODY></response>""".encode()


class KoicaPipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = connect(Path(self.tmp.name) / "real.db")
        initialize(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_live_transport_identifies_client_and_requests_xml(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"<RESPONSE />"
        with patch(
            "opportunity_radar.koica_pipeline.urllib.request.urlopen",
            return_value=response,
        ) as urlopen:
            body = KoicaCollector._default_transport("https://example.test/api")

        request = urlopen.call_args.args[0]
        self.assertEqual(body, b"<RESPONSE />")
        self.assertEqual(request.get_header("User-agent"), "KGlobalOpportunityRadar/0.1")
        self.assertEqual(request.get_header("Accept"), "application/xml")

    def test_collects_only_target_countries_and_keeps_raw_responses(self):
        def transport(url: str) -> bytes:
            parsed = urllib.parse.urlparse(url)
            if parsed.path.endswith("getBsnsInfoList"):
                return LIST_XML
            number = urllib.parse.parse_qs(parsed.query)["P_BSNS_NO"][0]
            return detail_xml(number)

        collector = KoicaCollector(self.conn, "test-key", transport=transport)
        counts = collector.collect(years=[2026], project_types=["0102"], page_size=100)
        self.assertEqual(counts, {"VNM": 1, "IDN": 1, "MNG": 1})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM project").fetchone()[0], 3)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM raw_api_response").fetchone()[0], 4)
        row = self.conn.execute("SELECT budget, recipient_name, raw_sector_code FROM project WHERE country_iso3='VNM'").fetchone()
        self.assertEqual(row["budget"], 1_000_000)
        self.assertEqual(row["recipient_name"], "Vietnam")
        self.assertEqual(row["raw_sector_code"], "EDU")
    def test_retries_transient_gateway_errors(self):
        list_attempts = 0
        delays: list[float] = []

        def transport(url: str) -> bytes:
            nonlocal list_attempts
            parsed = urllib.parse.urlparse(url)
            if parsed.path.endswith("getBsnsInfoList"):
                list_attempts += 1
                if list_attempts < 3:
                    raise urllib.error.HTTPError(url, 504, "Gateway Time-out", {}, None)
                return LIST_XML
            number = urllib.parse.parse_qs(parsed.query)["P_BSNS_NO"][0]
            return detail_xml(number)

        collector = KoicaCollector(
            self.conn,
            "test-key",
            transport=transport,
            sleeper=delays.append,
        )
        counts = collector.collect(years=[2026], project_types=["0102"], page_size=10)

        self.assertEqual(counts, {"VNM": 1, "IDN": 1, "MNG": 1})
        self.assertEqual(list_attempts, 3)
        self.assertEqual(delays, [10.0, 20.0])

    def test_resilient_collector_keeps_list_project_when_detail_is_unavailable(self):
        def transport(url: str) -> bytes:
            parsed = urllib.parse.urlparse(url)
            if parsed.path.endswith("getBsnsInfoList"):
                return LIST_XML
            raise RuntimeError("KOICA API error 99: unknown API error")

        collector = ResilientKoicaCollector(
            self.conn,
            "test-key",
            transport=transport,
        )
        counts = collector.collect(
            years=[2026],
            project_types=["0102"],
            page_size=100,
        )

        self.assertEqual(counts, {"VNM": 1, "IDN": 1, "MNG": 1})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM project").fetchone()[0], 3)
        self.assertEqual(
            self.conn.execute(
                "SELECT status FROM ingestion_run ORDER BY id DESC LIMIT 1"
            ).fetchone()[0],
            "partial",
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM data_quality_issue "
                "WHERE issue_type='api_slice_failed'"
            ).fetchone()[0],
            3,
        )

    def test_resilient_collector_supports_list_only_mode(self):
        detail_calls = 0

        def transport(url: str) -> bytes:
            nonlocal detail_calls
            parsed = urllib.parse.urlparse(url)
            if parsed.path.endswith("getBsnsInfoList"):
                return LIST_XML
            detail_calls += 1
            return detail_xml("VN-1")

        collector = ResilientKoicaCollector(
            self.conn,
            "test-key",
            transport=transport,
        )
        counts = collector.collect(
            years=[2026],
            project_types=["0102"],
            page_size=100,
            fetch_details=False,
        )

        self.assertEqual(counts, {"VNM": 1, "IDN": 1, "MNG": 1})
        self.assertEqual(detail_calls, 0)
        self.assertEqual(
            self.conn.execute(
                "SELECT status FROM ingestion_run ORDER BY id DESC LIMIT 1"
            ).fetchone()[0],
            "complete",
        )


if __name__ == "__main__":
    unittest.main()
