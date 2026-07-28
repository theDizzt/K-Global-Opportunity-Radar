from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from opportunity_radar.curated_policy import load_curated_policy_evidence
from opportunity_radar.db import connect, initialize


class CuratedPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.conn = connect(self.root / "policy.db")
        initialize(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def _write(self, payload: dict) -> Path:
        path = self.root / "policy.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_import_is_idempotent_and_syncs_source_labeled_signal(self) -> None:
        payload = {
            "records": [
                {
                    "external_id": "OFFICIAL-1",
                    "country_iso3": "VNM",
                    "title": "베트남 디지털 협력 MOU",
                    "event_date": "2026-01-02",
                    "event_type": "mou",
                    "sectors": ["digital"],
                    "organizations": ["MOFA", "Vietnam ministry"],
                    "supporting_text": "공식 디지털 협력 MOU 체결",
                    "source_url": "https://www.mofa.go.kr/official/1",
                }
            ]
        }
        path = self._write(payload)

        first = load_curated_policy_evidence(self.conn, path)
        second = load_curated_policy_evidence(self.conn, path)

        self.assertEqual(first["evidence_rows_upserted"], 1)
        self.assertEqual(second["evidence_rows_upserted"], 1)
        self.assertEqual(
            self.conn.execute(
                """SELECT COUNT(*) FROM evidence
                   WHERE event_type='mou'"""
            ).fetchone()[0],
            1,
        )
        signal = self.conn.execute(
            """SELECT event_tier, eligible_predictor FROM signal_event
               WHERE country_iso3='VNM' AND sector_code='digital'"""
        ).fetchone()
        self.assertEqual(tuple(signal), ("B", 1))

    def test_rejects_non_official_source_url(self) -> None:
        payload = {
            "records": [
                {
                    "external_id": "BAD-URL",
                    "country_iso3": "VNM",
                    "title": "unverified",
                    "event_date": "2026-01-02",
                    "event_type": "mou",
                    "sectors": ["digital"],
                    "organizations": [],
                    "supporting_text": "unverified",
                    "source_url": "https://example.com/not-official",
                }
            ]
        }
        with self.assertRaises(ValueError):
            load_curated_policy_evidence(self.conn, self._write(payload))


if __name__ == "__main__":
    unittest.main()
