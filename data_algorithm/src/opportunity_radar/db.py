from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .taxonomy_v2 import SECTORS

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS country (
    iso3 TEXT PRIMARY KEY,
    iso2 TEXT,
    name_ko TEXT NOT NULL,
    name_en TEXT,
    region_code TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sector (
    code TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    weights_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS source_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    published_at TEXT,
    source_url TEXT,
    raw_json TEXT,
    UNIQUE(source_type, external_id)
);

CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_record_id INTEGER REFERENCES source_record(id),
    external_id TEXT NOT NULL UNIQUE,
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    sector_code TEXT REFERENCES sector(code),
    name TEXT NOT NULL,
    start_year INTEGER,
    end_year INTEGER,
    budget REAL,
    status TEXT,
    agency TEXT,
    classification_confidence REAL
);

CREATE TABLE IF NOT EXISTS academic_program (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT NOT NULL UNIQUE,
    source_record_id INTEGER REFERENCES source_record(id),
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    university_name TEXT NOT NULL,
    bachelor INTEGER DEFAULT 0,
    master INTEGER DEFAULT 0,
    doctorate INTEGER DEFAULT 0,
    language_course INTEGER DEFAULT 0,
    research_center INTEGER DEFAULT 0,
    sejong_institute INTEGER DEFAULT 0,
    korea_corner INTEGER DEFAULT 0,
    reference_date TEXT
);

CREATE TABLE IF NOT EXISTS hallyu_stat (
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    year INTEGER NOT NULL,
    club_count INTEGER,
    member_count INTEGER,
    PRIMARY KEY(country_iso3, year)
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_record_id INTEGER NOT NULL REFERENCES source_record(id),
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    sector_code TEXT NOT NULL REFERENCES sector(code),
    event_type TEXT NOT NULL,
    event_date TEXT,
    organizations_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL,
    supporting_text TEXT NOT NULL,
    UNIQUE(source_record_id, sector_code, event_type)
);

CREATE TABLE IF NOT EXISTS safety_notice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT NOT NULL UNIQUE,
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    warning_level INTEGER NOT NULL,
    published_at TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT
);

CREATE TABLE IF NOT EXISTS source_coverage (
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    source_type TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    PRIMARY KEY(country_iso3, source_type)
);

CREATE TABLE IF NOT EXISTS score_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    sector_code TEXT NOT NULL REFERENCES sector(code),
    score_version TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    demand_score REAL NOT NULL,
    alignment_score REAL NOT NULL,
    readiness_score REAL NOT NULL,
    korea_base_score REAL NOT NULL,
    opportunity_score REAL NOT NULL,
    data_confidence REAL NOT NULL,
    risk_level INTEGER,
    sensitivity_low REAL,
    sensitivity_high REAL,
    UNIQUE(country_iso3, sector_code, score_version, as_of_date)
);

CREATE TABLE IF NOT EXISTS score_component (
    score_id INTEGER NOT NULL REFERENCES score_snapshot(id) ON DELETE CASCADE,
    component_code TEXT NOT NULL,
    raw_value REAL,
    normalized_value REAL,
    contribution REAL,
    detail_json TEXT,
    PRIMARY KEY(score_id, component_code)
);

CREATE INDEX IF NOT EXISTS idx_record_country ON source_record(country_iso3);
CREATE INDEX IF NOT EXISTS idx_project_country_sector ON project(country_iso3, sector_code);
CREATE INDEX IF NOT EXISTS idx_evidence_country_sector ON evidence(country_iso3, sector_code);
CREATE INDEX IF NOT EXISTS idx_score_sector ON score_snapshot(sector_code, opportunity_score DESC);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    academic_columns = {row[1] for row in conn.execute("PRAGMA table_info(academic_program)")}
    if "source_record_id" not in academic_columns:
        conn.execute(
            "ALTER TABLE academic_program ADD COLUMN source_record_id INTEGER REFERENCES source_record(id)"
        )
    conn.execute("UPDATE sector SET enabled=0")
    conn.executemany(
        "INSERT OR REPLACE INTO sector(code, name_ko, weights_json, enabled) VALUES (?, ?, ?, 1)",
        [(code, cfg["name_ko"], json.dumps(cfg["weights"], ensure_ascii=False)) for code, cfg in SECTORS.items()],
    )
    from .standards import ensure_standard_schema
    ensure_standard_schema(conn)
    from .sector_tags import backfill_record_sectors
    backfill_record_sectors(conn)
    from .analytics import ensure_analytics
    ensure_analytics(conn)
    from .statistical_signals import ensure_signal_schema
    ensure_signal_schema(conn)
    from .opportunity_models import ensure_opportunity_model_schema
    ensure_opportunity_model_schema(conn)
    from .donor_supply import ensure_donor_supply_schema
    ensure_donor_supply_schema(conn)
    conn.commit()
