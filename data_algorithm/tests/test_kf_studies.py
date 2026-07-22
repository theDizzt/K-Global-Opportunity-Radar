from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.kf_studies import KF_STUDIES_URL, load_kf_academic_html


class KfStudiesTest(unittest.TestCase):
    def test_loads_official_html_excel_shape_with_lineage(self):
        html = """<html><body><table>
        <tr><th>지역</th><th>국가</th><th>대학형태</th><th>대학명</th><th>한국학 제공 형태</th></tr>
        <tr><td>동남아</td><td>베트남</td><td>사립</td><td>테스트대학교</td><td>학사 석사 교양 센터</td></tr>
        </table></body></html>"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kf.xls"
            path.write_text(html, encoding="utf-8")
            conn = connect(Path(tmp) / "kf.db")
            initialize(conn)
            counts = load_kf_academic_html(conn, path)
            self.assertEqual(counts, {"VNM": 1, "IDN": 0, "MNG": 0})
            row = conn.execute(
                """SELECT a.*, r.source_url FROM academic_program a
                   JOIN source_record r ON r.id=a.source_record_id"""
            ).fetchone()
            self.assertEqual(row["country_iso3"], "VNM")
            self.assertEqual((row["bachelor"], row["master"], row["language_course"], row["research_center"]), (1, 1, 1, 1))
            self.assertEqual(row["source_url"], KF_STUDIES_URL)
            conn.close()


if __name__ == "__main__":
    unittest.main()
