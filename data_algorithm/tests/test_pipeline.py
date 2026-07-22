from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.explain import build_explanation_context, template_explanation
from opportunity_radar.ingest import load_demo_bundle
from opportunity_radar.scoring import calculate_scores, recommendations


ROOT = Path(__file__).resolve().parents[1]


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = connect(Path(self.tmp.name) / "radar.db")
        initialize(self.conn)
        load_demo_bundle(self.conn, ROOT / "data" / "demo_bundle.json")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_end_to_end_scores_all_country_sector_pairs(self):
        count = calculate_scores(self.conn, date(2026, 7, 16))
        self.assertEqual(count, 24)
        rows = recommendations(self.conn, "education", 3)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(0 <= r["opportunity_score"] <= 100 for r in rows))
        self.assertTrue(all(0 <= r["data_confidence"] <= 100 for r in rows))
        self.assertGreaterEqual(rows[0]["opportunity_score"], rows[1]["opportunity_score"])

    def test_score_is_reproducible(self):
        calculate_scores(self.conn, date(2026, 7, 16))
        first = [(r["country_iso3"], r["opportunity_score"]) for r in recommendations(self.conn, "education", 3)]
        calculate_scores(self.conn, date(2026, 7, 16))
        second = [(r["country_iso3"], r["opportunity_score"]) for r in recommendations(self.conn, "education", 3)]
        self.assertEqual(first, second)

    def test_explanation_only_references_loaded_evidence(self):
        calculate_scores(self.conn, date(2026, 7, 16))
        row = recommendations(self.conn, "education", 1)[0]
        context = build_explanation_context(self.conn, row["id"])
        explanation = template_explanation(context)
        valid = {e["evidence_id"] for e in context["evidence"]}
        self.assertTrue(set(explanation["evidence_ids"]).issubset(valid))
        self.assertIn(row["name_ko"], explanation["summary"])


if __name__ == "__main__":
    unittest.main()
