from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.ingest import load_demo_bundle
from opportunity_radar.scoring import (
    WEIGHT_PRESETS,
    calculate_scores,
    normalize_dimension_weights,
    recommend_with_options,
)


class RecommendationOptionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = connect(Path(self.tmp.name) / "recommend.db")
        initialize(self.conn)
        load_demo_bundle(self.conn, "data/demo_bundle.json")
        calculate_scores(self.conn, date(2026, 7, 16))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_region_country_and_risk_filters(self):
        rows = recommend_with_options(
            self.conn, "education", region="NEA", max_risk=1,
            min_confidence=0, weights=WEIGHT_PRESETS["enterprise"],
        )
        self.assertTrue(rows)
        self.assertEqual({row["country_iso3"] for row in rows}, {"MNG"})
        self.assertIn("top_components", rows[0])

    def test_custom_weights_are_normalized_and_validated(self):
        result = normalize_dimension_weights(
            {"demand": 2, "alignment": 1, "readiness": 1, "korea_base": 0}
        )
        self.assertEqual(sum(result.values()), 1)
        with self.assertRaises(ValueError):
            normalize_dimension_weights({"demand": 1})
        with self.assertRaises(ValueError):
            normalize_dimension_weights(
                {"demand": -1, "alignment": 1, "readiness": 1, "korea_base": 1}
            )


if __name__ == "__main__":
    unittest.main()
