from __future__ import annotations

import argparse
import json
import sys

from opportunity_radar.db import connect, initialize
from opportunity_radar.policy_evidence import (
    classify_policy_evidence,
    record_policy_review,
    reviewer_agreement,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List and review conservative Tier A/B policy candidates"
    )
    parser.add_argument("--db", default="data/statistical_signals_full.db")
    parser.add_argument(
        "--reviewer",
        help="Reviewer identifier required when approving or rejecting",
    )
    parser.add_argument(
        "--approve",
        action="append",
        type=int,
        default=[],
        help="Evidence ID to approve; repeat as needed",
    )
    parser.add_argument(
        "--reject",
        action="append",
        type=int,
        default=[],
        help="Evidence ID to reject; repeat as needed",
    )
    parser.add_argument(
        "--compare-reviewer",
        action="append",
        default=[],
        help="Reviewer compared with --reviewer using Cohen's kappa",
    )
    parser.add_argument(
        "--include-decided",
        action="store_true",
        help="Include already approved/rejected candidates in output",
    )
    args = parser.parse_args()
    overlap = set(args.approve) & set(args.reject)
    if overlap:
        parser.error(
            "The same evidence ID cannot be both approved and rejected: "
            + ", ".join(str(value) for value in sorted(overlap))
        )
    if (args.approve or args.reject) and not args.reviewer:
        parser.error("--reviewer is required with --approve or --reject")

    conn = connect(args.db)
    initialize(conn)
    classification = classify_policy_evidence(conn)
    for evidence_id in args.approve:
        record_policy_review(
            conn,
            evidence_id=evidence_id,
            reviewer_id=args.reviewer,
            approved=True,
        )
    for evidence_id in args.reject:
        record_policy_review(
            conn,
            evidence_id=evidence_id,
            reviewer_id=args.reviewer,
            approved=False,
        )
    classification = {
        row["review_status"]: row["count"]
        for row in conn.execute(
            """SELECT review_status, COUNT(*) AS count
               FROM policy_evidence_classification
               GROUP BY review_status
               ORDER BY review_status"""
        )
    }
    statuses = (
        (
            "review_required",
            "needs_adjudication",
            "human_approved",
            "human_rejected",
        )
        if args.include_decided
        else ("review_required",)
    )
    placeholders = ",".join("?" for _ in statuses)
    candidates = [
        dict(row)
        for row in conn.execute(
            f"""SELECT p.evidence_id, e.country_iso3, e.sector_code,
                       e.event_date, p.inferred_event_type, p.event_tier,
                       p.review_status, p.confidence, r.title,
                       e.supporting_text, r.source_url
                FROM policy_evidence_classification p
                JOIN evidence e ON e.id=p.evidence_id
                JOIN source_record r ON r.id=e.source_record_id
                WHERE p.review_status IN ({placeholders})
                ORDER BY e.event_date DESC, p.evidence_id""",
            statuses,
        )
    ]
    agreement = [
        reviewer_agreement(
            conn,
            reviewer_a=args.reviewer,
            reviewer_b=other,
        )
        for other in args.compare_reviewer
        if args.reviewer
    ]
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(
        json.dumps(
            {
                "classification_counts": classification,
                "approved_ids": args.approve,
                "rejected_ids": args.reject,
                "reviewer": args.reviewer,
                "reviewer_agreement": agreement,
                "candidates": candidates,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    conn.close()


if __name__ == "__main__":
    main()
