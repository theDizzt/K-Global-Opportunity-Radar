from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from contextlib import contextmanager
from itertools import chain
from pathlib import Path
from typing import Iterable, TextIO

from .taxonomy_v2 import classify_sector


PROJECT_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS project_master (
    project_uid TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_project_id TEXT NOT NULL,
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    sector_code TEXT NOT NULL REFERENCES sector(code),
    title TEXT NOT NULL,
    start_year INTEGER NOT NULL,
    end_year INTEGER,
    commitment_amount REAL,
    status TEXT,
    implementing_agency TEXT,
    is_new INTEGER NOT NULL DEFAULT 1,
    continuation_group TEXT,
    source_url TEXT,
    first_seen_at TEXT,
    raw_json TEXT,
    UNIQUE(source_type, source_project_id, country_iso3, sector_code)
);

CREATE INDEX IF NOT EXISTS idx_project_master_panel
ON project_master(country_iso3, sector_code, start_year);
"""


def ensure_project_history_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(PROJECT_HISTORY_SCHEMA)
    conn.commit()


def _stable_uid(source_type: str, source_id: str, country: str, sector: str) -> str:
    value = f"{source_type}|{source_id}|{country}|{sector}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _upsert_project(
    conn: sqlite3.Connection,
    *,
    source_type: str,
    source_project_id: str,
    country_iso3: str,
    sector_code: str,
    title: str,
    start_year: int,
    end_year: int | None = None,
    commitment_amount: float | None = None,
    status: str | None = None,
    implementing_agency: str | None = None,
    source_url: str | None = None,
    first_seen_at: str | None = None,
    raw: dict | None = None,
) -> None:
    uid = _stable_uid(source_type, source_project_id, country_iso3, sector_code)
    conn.execute(
        """INSERT INTO project_master(
               project_uid, source_type, source_project_id, country_iso3, sector_code,
               title, start_year, end_year, commitment_amount, status,
               implementing_agency, source_url, first_seen_at, raw_json
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(project_uid) DO UPDATE SET
             title=excluded.title,
             start_year=MIN(project_master.start_year, excluded.start_year),
             end_year=COALESCE(excluded.end_year, project_master.end_year),
             commitment_amount=COALESCE(excluded.commitment_amount, project_master.commitment_amount),
             status=COALESCE(excluded.status, project_master.status),
             implementing_agency=COALESCE(excluded.implementing_agency, project_master.implementing_agency),
             source_url=COALESCE(excluded.source_url, project_master.source_url),
             first_seen_at=COALESCE(project_master.first_seen_at, excluded.first_seen_at),
             raw_json=COALESCE(excluded.raw_json, project_master.raw_json)""",
        (
            uid,
            source_type,
            source_project_id,
            country_iso3,
            sector_code,
            title,
            start_year,
            end_year,
            commitment_amount,
            status,
            implementing_agency,
            source_url,
            first_seen_at,
            json.dumps(raw, ensure_ascii=False) if raw else None,
        ),
    )


def sync_internal_projects(conn: sqlite3.Connection) -> dict[str, int]:
    """Copy normalized KOICA and KF projects into the statistical outcome table."""
    ensure_project_history_schema(conn)
    counts = {"KOICA": 0, "KF": 0}
    project_columns = {row[1] for row in conn.execute("PRAGMA table_info(project)")}
    fetched_expression = "p.fetched_at" if "fetched_at" in project_columns else "NULL"

    koica_rows = conn.execute(
        f"""SELECT p.external_id, p.country_iso3,
                  COALESCE(p.sector_code, rs.sector_code) AS sector_code,
                  p.name, p.start_year, p.end_year, p.budget, p.status, p.agency,
                  r.source_url, COALESCE({fetched_expression}, l.collected_at) AS first_seen_at
           FROM project p
           JOIN source_record r ON r.id=p.source_record_id
           LEFT JOIN record_sector rs
             ON rs.source_record_id=r.id AND rs.is_primary=1
           LEFT JOIN record_lineage l ON l.source_record_id=r.id
           WHERE p.start_year IS NOT NULL
             AND COALESCE(p.sector_code, rs.sector_code) IS NOT NULL"""
    ).fetchall()
    for row in koica_rows:
        _upsert_project(
            conn,
            source_type="KOICA",
            source_project_id=row["external_id"],
            country_iso3=row["country_iso3"],
            sector_code=row["sector_code"],
            title=row["name"],
            start_year=int(row["start_year"]),
            end_year=row["end_year"],
            commitment_amount=row["budget"],
            status=row["status"],
            implementing_agency=row["agency"],
            source_url=row["source_url"],
            first_seen_at=row["first_seen_at"],
        )
        counts["KOICA"] += 1

    kf_rows = conn.execute(
        """SELECT r.external_id, r.country_iso3, rs.sector_code, r.title,
                  CAST(substr(r.published_at, 1, 4) AS INTEGER) AS start_year,
                  r.source_url, l.collected_at, r.raw_json
           FROM source_record r
           JOIN record_sector rs
             ON rs.source_record_id=r.id AND rs.is_primary=1
           LEFT JOIN record_lineage l ON l.source_record_id=r.id
           WHERE r.source_type='KF'
             AND r.external_id LIKE 'KF-BUS-%'
             AND r.published_at GLOB '[0-9][0-9][0-9][0-9]*'"""
    ).fetchall()
    for row in kf_rows:
        _upsert_project(
            conn,
            source_type="KF",
            source_project_id=row["external_id"],
            country_iso3=row["country_iso3"],
            sector_code=row["sector_code"],
            title=row["title"],
            start_year=int(row["start_year"]),
            implementing_agency="한국국제교류재단",
            source_url=row["source_url"],
            first_seen_at=row["collected_at"],
            raw=json.loads(row["raw_json"]) if row["raw_json"] else None,
        )
        counts["KF"] += 1

    conn.commit()
    return counts


def _normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


FIELD_ALIASES = {
    "project_id": (
        "crsid", "projectnumber", "projectid", "donorprojectnumber",
        "donorprojectno", "activityid",
    ),
    "donor": ("dedonorcode", "donorname", "donorcode", "donor", "providercode", "provider"),
    "country_iso3": ("derecipientcode", "recipientiso3", "countryiso3", "iso3"),
    "country_code": ("recipientcode", "recipient", "countrycode"),
    "country_name": ("recipientname", "countryname"),
    "title": ("projecttitle", "shortdescription", "title", "activityname"),
    "description": ("longdescription", "description", "projectdescription"),
    "purpose_code": ("purposecode", "sectorcode", "crspurposecode"),
    "purpose_name": ("purposename", "sectorname", "sector"),
    "start_date": ("expectedstartdate", "startdate", "projectstartdate"),
    "end_date": ("completiondate", "enddate", "projectenddate"),
    "year": ("year", "reportingyear", "timeperiod"),
    "amount": ("usdcommitment", "commitment", "commitmentamount", "value", "obsvalue"),
    "agency": ("agencyname", "extendingagency", "implementingagency", "channelname"),
}


def _find_value(row: dict[str, str], field: str) -> str:
    normalized = {_normalized_header(key): value for key, value in row.items()}
    for alias in FIELD_ALIASES[field]:
        value = normalized.get(alias)
        if value not in {None, ""}:
            return str(value).strip()
    return ""


def _year(value: str) -> int | None:
    match = re.search(r"(19|20)\d{2}", value or "")
    return int(match.group(0)) if match else None


def _number(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(",", "").strip())
    except ValueError:
        return None


def sector_from_purpose(
    purpose: str,
    text: str = "",
) -> tuple[str | None, float]:
    """Map an OECD CRS purpose code, with text fallback, to the shared taxonomy."""
    digits = re.sub(r"\D", "", purpose)
    code = int(digits[:5]) if len(digits) >= 5 else int(digits[:3]) if len(digits) >= 3 else None
    if code is not None:
        if 11100 <= code <= 11499 or 111 <= code <= 114:
            return ("vocational", 0.95) if code in {11330, 113} else ("education", 0.9)
        if 12000 <= code <= 13999 or 120 <= code <= 139:
            return "health", 0.9
        if 31100 <= code <= 31399 or 311 <= code <= 313:
            return "agriculture", 0.9
        if (
            14000 <= code <= 14999
            or 23000 <= code <= 23999
            or 41000 <= code <= 41999
            or code in {140, 230, 410}
        ):
            return "climate_environment", 0.85
        if 22000 <= code <= 22999 or code == 220:
            return "digital", 0.8
    return classify_sector(text)


def _sector_from_activity(row: dict[str, str]) -> tuple[str | None, float]:
    text = " ".join(
        (_find_value(row, "title"), _find_value(row, "description"), _find_value(row, "purpose_name"))
    )
    return sector_from_purpose(_find_value(row, "purpose_code"), text)


def _read_country_map(path: str | Path | None) -> dict[str, str]:
    if not path:
        return {}
    mapping: dict[str, str] = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            iso3 = str(row.get("iso3") or "").strip().upper()
            for key in ("raw_code", "raw_name", "country_code", "country_name", "iso3"):
                value = str(row.get(key) or "").strip()
                if value and iso3:
                    mapping[value.casefold()] = iso3
    return mapping


@contextmanager
def _activity_text(path: Path) -> Iterable[TextIO]:
    if path.suffix.casefold() == ".zip":
        archive = zipfile.ZipFile(path)
        names = [
            name for name in archive.namelist()
            if name.casefold().endswith((".txt", ".csv"))
        ]
        if len(names) != 1:
            archive.close()
            raise ValueError("Activity ZIP must contain exactly one CSV or TXT file")
        binary = archive.open(names[0])
        text = io.TextIOWrapper(binary, encoding="utf-8-sig", errors="replace", newline="")
        try:
            yield text
        finally:
            text.close()
            archive.close()
    else:
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as text:
            yield text


def load_activity_file(
    conn: sqlite3.Connection,
    path: str | Path,
    *,
    source_type: str = "OECD_CRS",
    country_map_path: str | Path | None = None,
    delimiter: str | None = None,
    korea_only: bool = True,
    source_url: str | None = None,
) -> dict[str, int]:
    """Load an OECD CRS-style CSV or pipe-delimited activity file.

    A country map with ``raw_code/raw_name/iso3`` columns can be supplied when
    the source does not include ISO3 recipient codes.
    """
    ensure_project_history_schema(conn)
    country_map = _read_country_map(country_map_path)
    path = Path(path)
    stats = {
        "loaded": 0,
        "skipped_donor": 0,
        "skipped_country": 0,
        "skipped_aggregate": 0,
        "skipped_sector": 0,
        "skipped_year": 0,
    }
    with _activity_text(path) as handle:
        header = handle.readline()
        chosen_delimiter = delimiter or ("|" if header.count("|") > header.count(",") else ",")
        reader = csv.DictReader(chain((header,), handle), delimiter=chosen_delimiter)
        for row in reader:
            donor = _find_value(row, "donor").casefold()
            if korea_only and donor and not any(token in donor for token in ("kor", "korea", "republic of korea")):
                stats["skipped_donor"] += 1
                continue

            raw_iso3 = _find_value(row, "country_iso3").upper()
            country_code = _find_value(row, "country_code")
            country_name = _find_value(row, "country_name")
            iso3 = raw_iso3 if re.fullmatch(r"[A-Z]{3}", raw_iso3) else None
            iso3 = iso3 or country_map.get(country_code.casefold()) or country_map.get(country_name.casefold())
            if not iso3:
                stats["skipped_country"] += 1
                continue

            country = conn.execute("SELECT 1 FROM country WHERE iso3=?", (iso3,)).fetchone()
            if not country:
                display_name = country_name or iso3
                conn.execute(
                    """INSERT INTO country(iso3, name_ko, name_en, region_code)
                       VALUES (?, ?, ?, 'UNKNOWN')""",
                    (iso3, display_name, display_name),
                )

            title = _find_value(row, "title")
            description = _find_value(row, "description")
            source_id = _find_value(row, "project_id")
            if not source_id and not title and not description:
                stats["skipped_aggregate"] += 1
                continue

            sector, confidence = _sector_from_activity(row)
            if not sector or confidence < 0.55:
                stats["skipped_sector"] += 1
                continue
            start_year = _year(_find_value(row, "start_date")) or _year(_find_value(row, "year"))
            if not start_year:
                stats["skipped_year"] += 1
                continue

            title = title or description or "Untitled activity"
            if not source_id:
                raw_id = f"{iso3}|{sector}|{title}|{_find_value(row, 'agency')}"
                source_id = hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:24]
            _upsert_project(
                conn,
                source_type=source_type,
                source_project_id=source_id,
                country_iso3=iso3,
                sector_code=sector,
                title=title,
                start_year=start_year,
                end_year=_year(_find_value(row, "end_date")),
                commitment_amount=_number(_find_value(row, "amount")),
                implementing_agency=_find_value(row, "agency") or None,
                source_url=source_url,
                raw=row,
            )
            stats["loaded"] += 1
    conn.commit()
    return stats


def project_sources(conn: sqlite3.Connection) -> Iterable[sqlite3.Row]:
    ensure_project_history_schema(conn)
    return conn.execute(
        """SELECT source_type, COUNT(*) AS project_count,
                  MIN(start_year) AS min_year, MAX(start_year) AS max_year
           FROM project_master GROUP BY source_type ORDER BY source_type"""
    ).fetchall()
