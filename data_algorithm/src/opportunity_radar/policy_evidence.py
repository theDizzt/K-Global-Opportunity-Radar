from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone

from .statistical_signals import TIER_BY_EVENT
from .taxonomy_v2 import SECTORS


POLICY_EVIDENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS policy_evidence_classification (
    evidence_id INTEGER PRIMARY KEY REFERENCES evidence(id) ON DELETE CASCADE,
    original_event_type TEXT NOT NULL,
    inferred_event_type TEXT,
    event_tier TEXT,
    classification_method TEXT NOT NULL,
    matched_pattern TEXT,
    sector_context_matched INTEGER NOT NULL,
    country_context_matched INTEGER NOT NULL,
    review_status TEXT NOT NULL,
    confidence REAL NOT NULL,
    classified_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_policy_classification_review
ON policy_evidence_classification(review_status, event_tier);

CREATE TABLE IF NOT EXISTS policy_evidence_review (
    evidence_id INTEGER NOT NULL
        REFERENCES policy_evidence_classification(evidence_id)
        ON DELETE CASCADE,
    reviewer_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('approve', 'reject')),
    reviewed_event_type TEXT,
    notes TEXT,
    reviewed_at TEXT NOT NULL,
    PRIMARY KEY(evidence_id, reviewer_id)
);

CREATE INDEX IF NOT EXISTS idx_policy_review_reviewer
ON policy_evidence_review(reviewer_id, decision);
"""


POLICY_PATTERNS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "implementation_agreement",
        "A",
        (
            r"시행\s*약정",
            r"사업\s*약정",
            r"implementation\s+agreement",
            r"record\s+of\s+discussions",
        ),
    ),
    (
        "budget_approval",
        "A",
        (
            r"예산(?:이|을|은)?\s*(?:승인|확정|배정)",
            r"budget\s+(?:was\s+)?(?:approved|allocated|confirmed)",
            r"funding\s+(?:was\s+)?approved",
        ),
    ),
    (
        "procurement",
        "A",
        (
            r"입찰\s*(?:공고|개시|착수)",
            r"조달\s*(?:공고|절차|계획|계약)",
            r"procurement\s+(?:notice|process|plan|contract)",
            r"invitation\s+to\s+bid",
        ),
    ),
    (
        "feasibility",
        "B",
        (
            r"(?:예비\s*)?타당성\s*조사",
            r"feasibility\s+stud(?:y|ies)",
        ),
    ),
    (
        "mou",
        "B",
        (
            r"양해\s*각서(?:를|에|가)?\s*(?:체결|서명|교환)",
            r"memorandum\s+of\s+understanding\s+(?:was\s+)?(?:signed|concluded)",
            r"\bMOU\s+(?:was\s+)?(?:signed|concluded)",
        ),
    ),
    (
        "agreement",
        "B",
        (
            r"(?:협정|협약)(?:을|에|이)?\s*(?:체결|서명|발효)",
            r"agreement\s+(?:was\s+)?(?:signed|concluded|entered\s+into\s+force)",
        ),
    ),
    (
        "working_group",
        "B",
        (
            r"(?:실무\s*협의|실무\s*회의|공동\s*위원회)(?:를|가|를\s*)?\s*(?:개최|출범)",
            r"working\s+group\s+(?:was\s+)?(?:launched|convened|established)",
        ),
    ),
    (
        "pilot",
        "B",
        (
            r"시범\s*사업(?:을|이)?\s*(?:착수|개시|실시|출범)",
            r"pilot\s+project\s+(?:was\s+)?(?:launched|started|implemented)",
        ),
    ),
)


def ensure_policy_evidence_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(POLICY_EVIDENCE_SCHEMA)
    conn.commit()


def _segments(text: str) -> list[str]:
    return [
        value.strip()
        for value in re.split(r"(?:\r?\n)+|(?<=[.!?。])\s+", text)
        if value.strip()
    ]


def _country_terms(conn: sqlite3.Connection, country: str) -> tuple[str, ...]:
    values = {
        str(row[0]).strip().casefold()
        for row in conn.execute(
            """SELECT alias FROM country_alias WHERE country_iso3=?
               UNION SELECT name_ko FROM country WHERE iso3=?
               UNION SELECT name_en FROM country WHERE iso3=?""",
            (country, country, country),
        )
        if row[0]
    }
    values.add(country.casefold())
    return tuple(sorted(values, key=len, reverse=True))


def _infer_candidate(
    text: str,
    *,
    country_terms: tuple[str, ...],
    sector_code: str,
) -> tuple[str | None, str | None, str | None, bool, bool]:
    sector_terms = tuple(
        str(term).casefold() for term in SECTORS.get(sector_code, {}).get("terms", ())
    )
    for segment in _segments(text):
        lowered = segment.casefold()
        for event_type, tier, patterns in POLICY_PATTERNS:
            for pattern in patterns:
                if not re.search(pattern, segment, flags=re.IGNORECASE):
                    continue
                sector_match = any(term in lowered for term in sector_terms)
                country_match = any(term in lowered for term in country_terms)
                if sector_match and country_match:
                    return (
                        event_type,
                        tier,
                        pattern,
                        sector_match,
                        country_match,
                    )
    return None, None, None, False, False


def classify_policy_evidence(conn: sqlite3.Connection) -> dict[str, int]:
    """Classify explicit policy actions without changing the source evidence.

    Source-labelled Tier A/B events are accepted. Events inferred from generic
    prose remain review candidates and are excluded from scores until a human
    changes ``review_status`` to ``human_approved``.
    """
    ensure_policy_evidence_schema(conn)
    rows = conn.execute(
        """SELECT e.id, e.country_iso3, e.sector_code, e.event_type,
                  e.confidence, e.supporting_text, r.title, r.source_type
           FROM evidence e JOIN source_record r ON r.id=e.source_record_id
           WHERE r.source_type IN ('LOD', 'MOFA')"""
    ).fetchall()
    classified_at = datetime.now(timezone.utc).isoformat()
    counts = {
        "source_labeled": 0,
        "review_required": 0,
        "not_policy_signal": 0,
    }
    for row in rows:
        original = str(row["event_type"])
        original_tier = TIER_BY_EVENT.get(original, "C")
        inferred: str | None = None
        tier: str | None = None
        pattern: str | None = None
        sector_match = False
        country_match = False
        if original_tier in {"A", "B"}:
            inferred = original
            tier = original_tier
            method = "source_event_type"
            review_status = "source_labeled"
            sector_match = True
            country_match = True
            confidence = float(row["confidence"])
        else:
            text = f"{row['title'] or ''}\n{row['supporting_text'] or ''}"
            inferred, tier, pattern, sector_match, country_match = (
                _infer_candidate(
                    text,
                    country_terms=_country_terms(
                        conn,
                        str(row["country_iso3"]),
                    ),
                    sector_code=str(row["sector_code"]),
                )
            )
            if inferred is not None:
                method = "conservative_pattern_candidate"
                review_status = "review_required"
                confidence = min(0.8, float(row["confidence"]) * 0.9)
            else:
                method = "no_qualifying_policy_action"
                review_status = "not_policy_signal"
                confidence = 0.0
        counts[review_status] += 1
        conn.execute(
            """INSERT INTO policy_evidence_classification(
                   evidence_id, original_event_type, inferred_event_type,
                   event_tier, classification_method, matched_pattern,
                   sector_context_matched, country_context_matched,
                   review_status, confidence, classified_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(evidence_id) DO UPDATE SET
                 original_event_type=excluded.original_event_type,
                 inferred_event_type=excluded.inferred_event_type,
                 event_tier=excluded.event_tier,
                 classification_method=excluded.classification_method,
                 matched_pattern=excluded.matched_pattern,
                 sector_context_matched=excluded.sector_context_matched,
                 country_context_matched=excluded.country_context_matched,
                 review_status=CASE
                   WHEN policy_evidence_classification.review_status='human_approved'
                   THEN 'human_approved'
                   WHEN policy_evidence_classification.review_status='human_rejected'
                   THEN 'human_rejected'
                   WHEN policy_evidence_classification.review_status='needs_adjudication'
                   THEN 'needs_adjudication'
                   ELSE excluded.review_status
                 END,
                 confidence=excluded.confidence,
                 classified_at=excluded.classified_at""",
            (
                int(row["id"]),
                original,
                inferred,
                tier,
                method,
                pattern,
                int(sector_match),
                int(country_match),
                review_status,
                confidence,
                classified_at,
            ),
        )
    conn.commit()
    counts = {
        "source_labeled": 0,
        "review_required": 0,
        "not_policy_signal": 0,
        "human_approved": 0,
        "human_rejected": 0,
        "needs_adjudication": 0,
    }
    for row in conn.execute(
        """SELECT review_status, COUNT(*)
           FROM policy_evidence_classification GROUP BY review_status"""
    ):
        counts[str(row[0])] = int(row[1])
    return counts


def set_policy_review_status(
    conn: sqlite3.Connection,
    *,
    evidence_id: int,
    approved: bool,
) -> None:
    """Persist an explicit human decision for one inferred policy candidate."""
    ensure_policy_evidence_schema(conn)
    row = conn.execute(
        """SELECT inferred_event_type, event_tier, review_status
           FROM policy_evidence_classification WHERE evidence_id=?""",
        (evidence_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown policy evidence candidate: {evidence_id}")
    if row["inferred_event_type"] is None or row["event_tier"] not in {"A", "B"}:
        raise ValueError("Only inferred Tier A/B candidates can be reviewed")
    conn.execute(
        """UPDATE policy_evidence_classification
           SET review_status=? WHERE evidence_id=?""",
        ("human_approved" if approved else "human_rejected", evidence_id),
    )
    conn.commit()


def _refresh_review_consensus(
    conn: sqlite3.Connection,
    evidence_id: int,
) -> str:
    row = conn.execute(
        """SELECT classification_method FROM policy_evidence_classification
           WHERE evidence_id=?""",
        (evidence_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown policy evidence candidate: {evidence_id}")
    if row["classification_method"] == "source_event_type":
        return "source_labeled"
    decisions = [
        str(value[0])
        for value in conn.execute(
            """SELECT decision FROM policy_evidence_review
               WHERE evidence_id=? ORDER BY reviewer_id""",
            (evidence_id,),
        )
    ]
    if len(decisions) < 2:
        status = "review_required"
    elif len(set(decisions)) > 1:
        status = "needs_adjudication"
    elif decisions[0] == "approve":
        status = "human_approved"
    else:
        status = "human_rejected"
    conn.execute(
        """UPDATE policy_evidence_classification SET review_status=?
           WHERE evidence_id=?""",
        (status, evidence_id),
    )
    return status


def record_policy_review(
    conn: sqlite3.Connection,
    *,
    evidence_id: int,
    reviewer_id: str,
    approved: bool,
    reviewed_event_type: str | None = None,
    notes: str | None = None,
) -> str:
    """Store one independent reviewer label and refresh consensus."""
    ensure_policy_evidence_schema(conn)
    reviewer = reviewer_id.strip()
    if not reviewer:
        raise ValueError("reviewer_id is required")
    candidate = conn.execute(
        """SELECT inferred_event_type, event_tier, classification_method
           FROM policy_evidence_classification WHERE evidence_id=?""",
        (evidence_id,),
    ).fetchone()
    if candidate is None:
        raise ValueError(f"Unknown policy evidence candidate: {evidence_id}")
    if (
        candidate["classification_method"] == "source_event_type"
        or candidate["inferred_event_type"] is None
        or candidate["event_tier"] not in {"A", "B"}
    ):
        raise ValueError("Only inferred Tier A/B candidates require review")
    event_type = reviewed_event_type or str(candidate["inferred_event_type"])
    if TIER_BY_EVENT.get(event_type) not in {"A", "B"}:
        raise ValueError("reviewed_event_type must be a Tier A/B event type")
    conn.execute(
        """INSERT INTO policy_evidence_review(
               evidence_id, reviewer_id, decision, reviewed_event_type,
               notes, reviewed_at
           ) VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(evidence_id, reviewer_id) DO UPDATE SET
             decision=excluded.decision,
             reviewed_event_type=excluded.reviewed_event_type,
             notes=excluded.notes,
             reviewed_at=excluded.reviewed_at""",
        (
            evidence_id,
            reviewer,
            "approve" if approved else "reject",
            event_type,
            notes,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    status = _refresh_review_consensus(conn, evidence_id)
    conn.commit()
    return status


def reviewer_agreement(
    conn: sqlite3.Connection,
    *,
    reviewer_a: str,
    reviewer_b: str,
) -> dict[str, object]:
    """Calculate Cohen's kappa over two reviewers' shared binary labels."""
    rows = conn.execute(
        """SELECT a.evidence_id, a.decision AS decision_a,
                  b.decision AS decision_b
           FROM policy_evidence_review a
           JOIN policy_evidence_review b
             ON b.evidence_id=a.evidence_id
           WHERE a.reviewer_id=? AND b.reviewer_id=?
           ORDER BY a.evidence_id""",
        (reviewer_a, reviewer_b),
    ).fetchall()
    n = len(rows)
    if n == 0:
        return {
            "reviewer_a": reviewer_a,
            "reviewer_b": reviewer_b,
            "shared_count": 0,
            "observed_agreement": None,
            "expected_agreement": None,
            "cohen_kappa": None,
        }
    observed = sum(
        row["decision_a"] == row["decision_b"] for row in rows
    ) / n
    a_approve = sum(row["decision_a"] == "approve" for row in rows) / n
    b_approve = sum(row["decision_b"] == "approve" for row in rows) / n
    expected = a_approve * b_approve + (1 - a_approve) * (1 - b_approve)
    kappa = (
        (observed - expected) / (1 - expected)
        if expected < 1.0
        else None
    )
    return {
        "reviewer_a": reviewer_a,
        "reviewer_b": reviewer_b,
        "shared_count": n,
        "observed_agreement": observed,
        "expected_agreement": expected,
        "cohen_kappa": kappa,
    }
