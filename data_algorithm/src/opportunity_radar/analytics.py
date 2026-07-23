from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


PROVIDERS = {
    "KOICA": "한국국제협력단",
    "KF": "한국국제교류재단",
    "MOFA": "외교부",
    "LOD": "외교부",
}


ANALYTICS_VIEWS = """
DROP VIEW IF EXISTS country_master;
CREATE VIEW country_master AS
SELECT c.iso3, c.iso2, c.name_ko, c.name_en, c.region_code,
       GROUP_CONCAT(a.alias, '|') AS aliases
FROM country c LEFT JOIN country_alias a ON a.country_iso3=c.iso3
GROUP BY c.iso3, c.iso2, c.name_ko, c.name_en, c.region_code;

DROP VIEW IF EXISTS oda_project_fact;
CREATE VIEW oda_project_fact AS
SELECT p.external_id, p.country_iso3, rs.sector_code, rs.is_primary,
       p.name, p.start_year, p.end_year, p.budget, p.status, p.agency,
       p.classification_confidence, r.id AS source_record_id,
       r.published_at AS reference_date, r.source_url
FROM project p
JOIN source_record r ON r.id=p.source_record_id
LEFT JOIN record_sector rs ON rs.source_record_id=r.id;

DROP VIEW IF EXISTS diplomatic_activity_fact;
CREATE VIEW diplomatic_activity_fact AS
SELECT e.id AS evidence_id, e.country_iso3, e.sector_code, e.event_type,
       e.event_date, e.organizations_json, e.confidence, e.supporting_text,
       r.source_type, r.external_id, r.title, r.source_url,
       COALESCE(l.provider_name,
         CASE r.source_type WHEN 'MOFA' THEN '외교부' WHEN 'LOD' THEN '외교부'
              WHEN 'KF' THEN '한국국제교류재단' WHEN 'KOICA' THEN '한국국제협력단' END
       ) AS provider_name
FROM evidence e JOIN source_record r ON r.id=e.source_record_id
LEFT JOIN record_lineage l ON l.source_record_id=r.id;

DROP VIEW IF EXISTS korea_base_fact;
CREATE VIEW korea_base_fact AS
SELECT a.country_iso3, 'academic_program' AS base_type, a.external_id,
       a.university_name AS organization_name, a.reference_date,
       bachelor, master, doctorate, language_course, research_center,
       sejong_institute, korea_corner, NULL AS year,
       NULL AS club_count, NULL AS member_count,
       r.source_url, COALESCE(l.provider_name, 'KF') AS provider_name
FROM academic_program a
LEFT JOIN source_record r ON r.id=a.source_record_id
LEFT JOIN record_lineage l ON l.source_record_id=r.id
UNION ALL
SELECT country_iso3, 'hallyu_stat', 'KF-HALLYU-' || country_iso3 || '-' || year,
       '한국국제교류재단', printf('%04d-01-01', year),
       NULL, NULL, NULL, NULL, NULL, NULL, NULL, year, club_count, member_count,
       NULL, 'KF'
FROM hallyu_stat;

DROP VIEW IF EXISTS risk_fact;
CREATE VIEW risk_fact AS
SELECT external_id, country_iso3, warning_level, published_at AS reference_date,
       title, source_url, '외교부' AS provider_name
FROM safety_notice;

DROP VIEW IF EXISTS cooperation_signal_yearly;
CREATE VIEW cooperation_signal_yearly AS
SELECT country_iso3, sector_code, signal_year,
       SUM(project_count) AS project_count,
       SUM(project_budget) AS project_budget,
       SUM(event_count) AS event_count,
       SUM(event_strength) AS event_strength
FROM (
  SELECT p.country_iso3, rs.sector_code, p.start_year AS signal_year,
         COUNT(DISTINCT p.id) AS project_count,
         SUM(COALESCE(p.budget, 0)) AS project_budget,
         0 AS event_count, 0.0 AS event_strength
  FROM project p JOIN record_sector rs ON rs.source_record_id=p.source_record_id
  WHERE p.start_year IS NOT NULL
  GROUP BY p.country_iso3, rs.sector_code, p.start_year
  UNION ALL
  SELECT e.country_iso3, rs.sector_code,
         CAST(substr(e.event_date, 1, 4) AS INTEGER),
         0, 0.0, COUNT(DISTINCT e.id), SUM(e.confidence)
  FROM evidence e JOIN record_sector rs ON rs.source_record_id=e.source_record_id
  WHERE e.event_date IS NOT NULL
  GROUP BY e.country_iso3, rs.sector_code, CAST(substr(e.event_date, 1, 4) AS INTEGER)
)
GROUP BY country_iso3, sector_code, signal_year;

DROP VIEW IF EXISTS evidence_document;
CREATE VIEW evidence_document AS
SELECT r.id AS source_record_id, r.source_type, r.external_id, r.country_iso3,
       rs.sector_code, rs.confidence AS sector_confidence, rs.is_primary,
       r.title, r.body, r.published_at AS reference_date, r.source_url,
       l.provider_name, l.collected_at, l.date_precision, l.quality_status
FROM source_record r
LEFT JOIN record_sector rs ON rs.source_record_id=r.id
LEFT JOIN record_lineage l ON l.source_record_id=r.id;
"""


def _date_precision(value: str | None) -> str:
    if not value:
        return "unknown"
    if len(value) >= 10:
        return "day"
    if len(value) >= 7:
        return "month"
    if len(value) >= 4:
        return "year"
    return "unknown"


def backfill_lineage(conn: sqlite3.Connection) -> int:
    collected_at = datetime.now(timezone.utc).isoformat()
    rows = conn.execute("SELECT id, source_type, published_at, source_url FROM source_record").fetchall()
    for row in rows:
        quality = "accepted" if row["source_url"] else "unreviewed"
        conn.execute(
            """INSERT INTO record_lineage(source_record_id, provider_name, collected_at,
                       reference_date, date_precision, transformation_version, quality_status)
               VALUES (?, ?, ?, ?, ?, 'clean-v2', ?)
               ON CONFLICT(source_record_id) DO UPDATE SET
                 provider_name=excluded.provider_name,
                 reference_date=excluded.reference_date,
                 date_precision=excluded.date_precision,
                 transformation_version=excluded.transformation_version,
                 quality_status=excluded.quality_status""",
            (
                row["id"], PROVIDERS.get(row["source_type"], row["source_type"]),
                collected_at, row["published_at"], _date_precision(row["published_at"]), quality,
            ),
        )
    return len(rows)


def ensure_analytics(conn: sqlite3.Connection) -> None:
    backfill_lineage(conn)
    conn.executescript(ANALYTICS_VIEWS)
