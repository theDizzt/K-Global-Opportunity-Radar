from __future__ import annotations

import tempfile
import unittest
import urllib.parse
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.koica_pipeline import KoicaCollector
from tests.test_koica_pipeline import LIST_XML, detail_xml


class KoicaRateLimitTest(unittest.TestCase):
    def test_spaces_successful_list_and_detail_requests(self):
        clock = [0.0]
        delays: list[float] = []
        starts: list[float] = []

        def sleeper(seconds: float) -> None:
            delays.append(seconds)
            clock[0] += seconds

        def transport(url: str) -> bytes:
            starts.append(clock[0])
            parsed = urllib.parse.urlparse(url)
            if parsed.path.endswith("getBsnsInfoList"):
                return LIST_XML
            number = urllib.parse.parse_qs(parsed.query)["P_BSNS_NO"][0]
            return detail_xml(number)

        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(Path(tmp) / "rate.db")
            initialize(conn)
            collector = KoicaCollector(
                conn,
                "test-key",
                transport=transport,
                sleeper=sleeper,
                min_request_interval=3.0,
                retry_jitter_seconds=0,
                monotonic=lambda: clock[0],
            )
            collector.collect(years=[2026], project_types=["0102"], page_size=100)
            conn.close()

        self.assertEqual(starts, [0.0, 3.0, 6.0])
        self.assertEqual(delays, [3.0, 3.0])


if __name__ == "__main__":
    unittest.main()
