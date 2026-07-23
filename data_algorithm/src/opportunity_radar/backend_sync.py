from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


SECTOR_TO_FIELD = {
    "education": "교육",
    "health": "보건",
    "digital": "디지털",
    "climate_environment": "기후·환경",
    "culture_content": "문화·한류",
    "vocational": "청년취업",
}

DOCUMENT_SECTOR_TO_FIELD = {
    **SECTOR_TO_FIELD,
    "agriculture": "농업",
    "korean_studies": "문화·한류",
}

SOURCE_CODE_MAP = {
    "LOD": "MOFA",
    "MOFA": "MOFA",
    "KOICA": "KOICA",
    "KF": "KF",
}


@dataclass(frozen=True)
class BackendSyncResult:
    scores: int
    documents: int
    skipped_scores: int
    skipped_documents: int


def sync_backend(
    algorithm_database: str | Path,
    backend_database: str | Path,
    *,
    as_of_date: str | None = None,
    is_demo: bool = False,
) -> BackendSyncResult:
    """Copy calculated scores and evidence into the FastAPI backend database."""
    algorithm = sqlite3.connect(algorithm_database)
    backend = sqlite3.connect(backend_database)
    algorithm.row_factory = sqlite3.Row
    backend.row_factory = sqlite3.Row
    backend.execute("PRAGMA foreign_keys = ON")
    try:
        supported_countries = {
            row["iso3"] for row in backend.execute("SELECT iso3 FROM countries")
        }
        supported_sources = {
            row["code"] for row in backend.execute("SELECT code FROM data_sources")
        }
        score_count, skipped_scores = _sync_scores(
            algorithm,
            backend,
            supported_countries,
            as_of_date,
            is_demo,
        )
        document_count, skipped_documents = _sync_documents(
            algorithm,
            backend,
            supported_countries,
            supported_sources,
        )
        backend.commit()
        return BackendSyncResult(
            scores=score_count,
            documents=document_count,
            skipped_scores=skipped_scores,
            skipped_documents=skipped_documents,
        )
    except Exception:
        backend.rollback()
        raise
    finally:
        algorithm.close()
        backend.close()


def _sync_scores(algorithm, backend, supported_countries, as_of_date, is_demo):
    clauses = [
        """s.as_of_date = (
            SELECT MAX(latest.as_of_date)
            FROM score_snapshot AS latest
            WHERE latest.country_iso3 = s.country_iso3
              AND latest.sector_code = s.sector_code
              AND latest.score_version = s.score_version
        )"""
    ]
    parameters: list[str] = []
    if as_of_date is not None:
        clauses = ["s.as_of_date = ?"]
        parameters.append(as_of_date)
    rows = algorithm.execute(
        f"""
        SELECT s.* FROM score_snapshot AS s
        WHERE {' AND '.join(clauses)}
        ORDER BY s.country_iso3, s.sector_code
        """,
        parameters,
    ).fetchall()
    written = 0
    skipped = 0
    for row in rows:
        field = SECTOR_TO_FIELD.get(row["sector_code"])
        if field is None or row["country_iso3"] not in supported_countries:
            skipped += 1
            continue
        backend.execute(
            """
            INSERT INTO opportunity_scores (
                country_iso3, field, score_version, as_of_date,
                demand_score, policy_alignment_score, readiness_score,
                korean_base_score, opportunity_score, data_confidence,
                is_demo, risk_level, sensitivity_low, sensitivity_high
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(country_iso3, field, score_version, as_of_date) DO UPDATE SET
                demand_score = excluded.demand_score,
                policy_alignment_score = excluded.policy_alignment_score,
                readiness_score = excluded.readiness_score,
                korean_base_score = excluded.korean_base_score,
                opportunity_score = excluded.opportunity_score,
                data_confidence = excluded.data_confidence,
                is_demo = excluded.is_demo,
                risk_level = excluded.risk_level,
                sensitivity_low = excluded.sensitivity_low,
                sensitivity_high = excluded.sensitivity_high
            """,
            (
                row["country_iso3"],
                field,
                row["score_version"],
                row["as_of_date"],
                row["demand_score"],
                row["alignment_score"],
                row["readiness_score"],
                row["korea_base_score"],
                row["opportunity_score"],
                row["data_confidence"],
                int(is_demo),
                row["risk_level"],
                row["sensitivity_low"],
                row["sensitivity_high"],
            ),
        )
        written += 1
    return written, skipped


def _sync_documents(algorithm, backend, supported_countries, supported_sources):
    if not _table_exists(algorithm, "record_sector"):
        return 0, 0
    rows = algorithm.execute(
        """
        SELECT r.source_type, r.external_id, r.country_iso3, r.title, r.body,
               r.published_at, r.source_url, rs.sector_code
        FROM source_record AS r
        LEFT JOIN record_sector AS rs ON rs.source_record_id = r.id
        ORDER BY r.id, rs.is_primary DESC, rs.sector_code
        """
    ).fetchall()
    collected_at = datetime.now(timezone.utc).isoformat()
    seen: set[tuple[str, str]] = set()
    written = 0
    skipped = 0
    for row in rows:
        source_code = SOURCE_CODE_MAP.get(row["source_type"])
        field = DOCUMENT_SECTOR_TO_FIELD.get(row["sector_code"], "외교 일반")
        key = (row["source_type"], row["external_id"])
        if key in seen:
            continue
        seen.add(key)
        if (
            source_code not in supported_sources
            or row["country_iso3"] not in supported_countries
            or not row["source_url"]
        ):
            skipped += 1
            continue
        document_uri = f"algorithm:{row['source_type']}:{row['external_id']}"
        backend.execute(
            """
            INSERT INTO source_documents (
                document_uri, source_code, dataset_code, title, summary,
                published_date, source_url, primary_field, collected_at,
                raw_payload_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(document_uri) DO UPDATE SET
                title = excluded.title,
                summary = excluded.summary,
                published_date = excluded.published_date,
                source_url = excluded.source_url,
                primary_field = excluded.primary_field,
                collected_at = excluded.collected_at
            """,
            (
                document_uri,
                source_code,
                f"algorithm_{row['source_type'].lower()}",
                row["title"],
                row["body"] or "",
                row["published_at"],
                row["source_url"],
                field,
                collected_at,
            ),
        )
        backend.execute(
            """
            INSERT OR IGNORE INTO document_countries (document_uri, country_iso3)
            VALUES (?, ?)
            """,
            (document_uri, row["country_iso3"]),
        )
        written += 1
    return written, skipped


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (name,),
    ).fetchone() is not None
