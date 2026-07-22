from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.standards import resolve_country_iso3
from opportunity_radar.taxonomy_v2 import classify_sector


class KoreanIntegrityTest(unittest.TestCase):
    def test_country_display_names_and_aliases_are_not_corrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(Path(tmp) / "integrity.db")
            initialize(conn)
            actual = dict(conn.execute("SELECT iso3, name_ko FROM country"))
            self.assertEqual(actual, {"VNM": "베트남", "IDN": "인도네시아", "MNG": "몽골"})
            self.assertEqual(resolve_country_iso3(conn, "베트남"), "VNM")
            self.assertEqual(resolve_country_iso3(conn, "인도네시아"), "IDN")
            self.assertEqual(resolve_country_iso3(conn, "몽골"), "MNG")
            conn.close()

    def test_korean_sector_examples(self):
        cases = {
            "교원 연수와 학교 교육과정 개선": "education",
            "전자정부와 인공지능 데이터 플랫폼": "digital",
            "감염병 진단과 공중보건": "health",
            "농촌 관개와 식량안보": "agriculture",
            "산림복원과 탄소감축": "climate_environment",
            "직업훈련과 취업 역량강화": "vocational",
            "해외대학 한국어와 한국학 과정": "korean_studies",
            "한류 영화와 문화콘텐츠 교류": "culture_content",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(classify_sector(text)[0], expected)


if __name__ == "__main__":
    unittest.main()
