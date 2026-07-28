from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.policy_evidence import (
    classify_policy_evidence,
    record_policy_review,
    reviewer_agreement,
    set_policy_review_status,
)


class PolicyEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = connect(Path(self.temp_dir.name) / "policy.db")
        initialize(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def _evidence(
        self,
        *,
        external_id: str,
        event_type: str,
        text: str,
    ) -> int:
        record = self.conn.execute(
            """INSERT INTO source_record(
                   source_type, external_id, country_iso3, title, published_at
               ) VALUES ('LOD', ?, 'VNM', '베트남 디지털 협력', '2026-01-01')""",
            (external_id,),
        )
        evidence = self.conn.execute(
            """INSERT INTO evidence(
                   source_record_id, country_iso3, sector_code, event_type,
                   event_date, confidence, supporting_text
               ) VALUES (?, 'VNM', 'digital', ?, '2026-01-01', 0.9, ?)""",
            (record.lastrowid, event_type, text),
        )
        return int(evidence.lastrowid)

    def test_accepts_source_label_but_requires_review_for_text_inference(self) -> None:
        accepted = self._evidence(
            external_id="EXPLICIT",
            event_type="mou",
            text="베트남 디지털 협력 양해각서를 체결했다.",
        )
        candidate = self._evidence(
            external_id="GENERIC",
            event_type="press_mention",
            text="한국과 베트남은 디지털 시범사업을 착수했다.",
        )
        unrelated = self._evidence(
            external_id="UNRELATED",
            event_type="press_mention",
            text="아세안 디지털 협력 MOU 체결 성과를 평가했다.",
        )
        self.conn.commit()

        result = classify_policy_evidence(self.conn)

        self.assertEqual(result["source_labeled"], 1)
        self.assertEqual(result["review_required"], 1)
        rows = {
            row["evidence_id"]: row
            for row in self.conn.execute(
                "SELECT * FROM policy_evidence_classification"
            )
        }
        self.assertEqual(rows[accepted]["review_status"], "source_labeled")
        self.assertEqual(rows[accepted]["event_tier"], "B")
        self.assertEqual(rows[candidate]["review_status"], "review_required")
        self.assertEqual(rows[candidate]["inferred_event_type"], "pilot")
        self.assertEqual(rows[unrelated]["review_status"], "not_policy_signal")

    def test_preserves_human_review_decision_on_reclassification(self) -> None:
        evidence_id = self._evidence(
            external_id="REVIEW",
            event_type="press_mention",
            text="한국과 베트남은 디지털 타당성 조사를 실시했다.",
        )
        self.conn.commit()
        classify_policy_evidence(self.conn)
        set_policy_review_status(
            self.conn,
            evidence_id=evidence_id,
            approved=True,
        )

        classify_policy_evidence(self.conn)

        status = self.conn.execute(
            """SELECT review_status FROM policy_evidence_classification
               WHERE evidence_id=?""",
            (evidence_id,),
        ).fetchone()[0]
        self.assertEqual(status, "human_approved")

    def test_rejects_review_of_non_policy_evidence(self) -> None:
        evidence_id = self._evidence(
            external_id="NOT-POLICY",
            event_type="press_mention",
            text="베트남 디지털 산업에 관한 일반적인 연구 보고서다.",
        )
        self.conn.commit()
        classify_policy_evidence(self.conn)

        with self.assertRaises(ValueError):
            set_policy_review_status(
                self.conn,
                evidence_id=evidence_id,
                approved=False,
            )

    def test_two_reviewer_consensus_and_cohen_kappa(self) -> None:
        first = self._evidence(
            external_id="DOUBLE-1",
            event_type="press_mention",
            text="한국과 베트남은 디지털 타당성 조사를 실시했다.",
        )
        second = self._evidence(
            external_id="DOUBLE-2",
            event_type="press_mention",
            text="한국과 베트남은 디지털 시범사업을 착수했다.",
        )
        self.conn.commit()
        classify_policy_evidence(self.conn)

        record_policy_review(
            self.conn,
            evidence_id=first,
            reviewer_id="analyst-a",
            approved=True,
        )
        status = record_policy_review(
            self.conn,
            evidence_id=first,
            reviewer_id="analyst-b",
            approved=True,
        )
        self.assertEqual(status, "human_approved")
        record_policy_review(
            self.conn,
            evidence_id=second,
            reviewer_id="analyst-a",
            approved=False,
        )
        status = record_policy_review(
            self.conn,
            evidence_id=second,
            reviewer_id="analyst-b",
            approved=True,
        )
        self.assertEqual(status, "needs_adjudication")

        agreement = reviewer_agreement(
            self.conn,
            reviewer_a="analyst-a",
            reviewer_b="analyst-b",
        )
        self.assertEqual(agreement["shared_count"], 2)
        self.assertAlmostEqual(agreement["observed_agreement"], 0.5)
        self.assertAlmostEqual(agreement["cohen_kappa"], 0.0)


if __name__ == "__main__":
    unittest.main()
