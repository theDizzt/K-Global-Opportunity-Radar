from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.standards import resolve_country_iso3
from opportunity_radar.taxonomy_v2 import SECTORS, canonical_sector, classify_sector


class StandardsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = connect(Path(self.tmp.name) / "standards.db")
        initialize(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_country_aliases_resolve_to_iso3(self):
        for alias in ("Vietnam", "Viet Nam", "VietNam", "베트남", "Việt Nam", "VN", "VNM"):
            self.assertEqual(resolve_country_iso3(self.conn, alias), "VNM")
        self.assertEqual(resolve_country_iso3(self.conn, "Republic of Indonesia"), "IDN")
        self.assertEqual(resolve_country_iso3(self.conn, "Монгол Улс"), "MNG")
        self.assertIsNone(resolve_country_iso3(self.conn, "unknown-country"))

    def test_eight_sector_taxonomy_and_priority_examples(self):
        self.assertEqual(len(SECTORS), 8)
        cases = {
            "교원 연수와 학교 교육과정 개선": "education",
            "전자정부와 인공지능 데이터 플랫폼": "digital",
            "감염병 진단과 공중보건": "health",
            "농촌 관개와 식량안보": "agriculture",
            "산림복원과 탄소감축": "climate_environment",
            "TVET 직업훈련과 취업 역량강화": "vocational",
            "해외대학 한국어와 한국학 과정": "korean_studies",
            "한류 영화와 문화콘텐츠 교류": "culture_content",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(classify_sector(text)[0], expected)

    def test_legacy_sector_codes_are_migrated(self):
        self.assertEqual(canonical_sector("climate_agri", "농촌 농업 사업")[0], "agriculture")
        self.assertEqual(canonical_sector("climate_agri", "산림 기후 사업")[0], "climate_environment")
        self.assertEqual(canonical_sector("korean_culture", "한국어 한국학 과정")[0], "korean_studies")
        self.assertEqual(canonical_sector("korean_culture", "한류 문화 공연")[0], "culture_content")


if __name__ == "__main__":
    unittest.main()
