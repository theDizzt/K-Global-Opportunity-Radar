from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from .taxonomy_v2 import canonical_sector, classify_sector


def _upsert_country(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO country(iso3, iso2, name_ko, name_en, region_code)
           VALUES (:iso3, :iso2, :name_ko, :name_en, :region_code)""",
        row,
    )


def _source_record(conn: sqlite3.Connection, *, source: str, external_id: str, country: str,
                   title: str, body: str = "", published_at: str | None = None,
                   url: str | None = None, raw: dict | None = None) -> int:
    conn.execute(
        """INSERT INTO source_record(source_type, external_id, country_iso3, title, body,
                   published_at, source_url, raw_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(source_type, external_id) DO UPDATE SET
             country_iso3=excluded.country_iso3, title=excluded.title, body=excluded.body,
             published_at=excluded.published_at, source_url=excluded.source_url, raw_json=excluded.raw_json""",
        (source, external_id, country, title, body, published_at, url,
         json.dumps(raw, ensure_ascii=False) if raw else None),
    )
    record_id = conn.execute(
        "SELECT id FROM source_record WHERE source_type=? AND external_id=?", (source, external_id)
    ).fetchone()[0]
    from .sector_tags import upsert_record_sectors
    upsert_record_sectors(conn, record_id, f"{title}\n{body}")
    return record_id


def _coverage(conn: sqlite3.Connection, country: str, source: str, count: int, observed_at: str) -> None:
    conn.execute(
        """INSERT INTO source_coverage(country_iso3, source_type, observed_at, record_count)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(country_iso3, source_type) DO UPDATE SET
             observed_at=excluded.observed_at, record_count=excluded.record_count""",
        (country, source, observed_at, count),
    )


def load_demo_bundle(conn: sqlite3.Connection, path: str | Path) -> None:
    bundle = json.loads(Path(path).read_text(encoding="utf-8"))
    as_of = bundle["as_of_date"]
    for country in bundle["countries"]:
        _upsert_country(conn, country)

    counts: dict[tuple[str, str], int] = {}
    for project in bundle["projects"]:
        sector, confidence = canonical_sector(project.get("sector_code"), project["name"])
        record_id = _source_record(
            conn, source="KOICA", external_id=project["external_id"],
            country=project["country_iso3"], title=project["name"],
            published_at=f'{project["start_year"]}-01-01', raw=project,
        )
        conn.execute(
            """INSERT INTO project(source_record_id, external_id, country_iso3, sector_code, name,
                       start_year, end_year, budget, status, agency, classification_confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(external_id) DO UPDATE SET sector_code=excluded.sector_code,
                 budget=excluded.budget, status=excluded.status, agency=excluded.agency""",
            (record_id, project["external_id"], project["country_iso3"], sector, project["name"],
             project["start_year"], project["end_year"], project["budget"], project["status"],
             project["agency"], confidence),
        )
        counts[(project["country_iso3"], "KOICA")] = counts.get((project["country_iso3"], "KOICA"), 0) + 1

    for item in bundle["diplomatic_events"]:
        record_id = _source_record(
            conn, source=item["source"], external_id=item["external_id"], country=item["country_iso3"],
            title=item["title"], body=item["supporting_text"], published_at=item["event_date"],
            url=item.get("source_url"), raw=item,
        )
        sector, _ = canonical_sector(
            item.get("sector_code"), f'{item["title"]} {item["supporting_text"]}'
        )
        conn.execute(
            """INSERT INTO evidence(source_record_id, country_iso3, sector_code, event_type, event_date,
                       organizations_json, confidence, supporting_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_record_id, sector_code, event_type) DO UPDATE SET
                 confidence=excluded.confidence, supporting_text=excluded.supporting_text""",
            (record_id, item["country_iso3"], sector, item["event_type"], item["event_date"],
             json.dumps(item.get("organizations", []), ensure_ascii=False), item["confidence"],
             item["supporting_text"]),
        )
        key = (item["country_iso3"], item["source"])
        counts[key] = counts.get(key, 0) + 1

    for p in bundle["academic_programs"]:
        conn.execute(
            """INSERT INTO academic_program(external_id, country_iso3, university_name, bachelor,
                       master, doctorate, language_course, research_center, sejong_institute,
                       korea_corner, reference_date)
               VALUES (:external_id, :country_iso3, :university_name, :bachelor, :master, :doctorate,
                       :language_course, :research_center, :sejong_institute, :korea_corner, :reference_date)
               ON CONFLICT(external_id) DO UPDATE SET reference_date=excluded.reference_date""",
            p,
        )
        counts[(p["country_iso3"], "KF")] = counts.get((p["country_iso3"], "KF"), 0) + 1

    for h in bundle["hallyu_stats"]:
        conn.execute(
            "INSERT OR REPLACE INTO hallyu_stat(country_iso3, year, club_count, member_count) VALUES (:country_iso3, :year, :club_count, :member_count)",
            h,
        )
        counts[(h["country_iso3"], "KF")] = counts.get((h["country_iso3"], "KF"), 0) + 1

    for s in bundle["safety_notices"]:
        conn.execute(
            """INSERT OR REPLACE INTO safety_notice(external_id, country_iso3, warning_level,
                       published_at, title, source_url)
               VALUES (:external_id, :country_iso3, :warning_level, :published_at, :title, :source_url)""",
            s,
        )
        counts[(s["country_iso3"], "MOFA")] = counts.get((s["country_iso3"], "MOFA"), 0) + 1

    for (country, source), count in counts.items():
        _coverage(conn, country, source, count, as_of)
    conn.commit()


def load_kf_academic_csv(conn: sqlite3.Connection, path: str | Path, country_map: dict[str, str]) -> int:
    """Load an official KF export after mapping Korean country names to ISO3."""
    aliases = {
        "country": ["국가", "국가명"], "university": ["대학명", "학교명"],
        "bachelor": ["학사"], "master": ["석사"], "doctorate": ["박사"],
        "language_course": ["교양/어학원", "교양어학원"], "research_center": ["한국연구센터", "연구센터"],
        "sejong_institute": ["세종학당"], "korea_corner": ["코리아코너"],
    }
    def value(row: dict, key: str, default=""):
        return next((row[name] for name in aliases[key] if name in row), default)
    count = 0
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            iso3 = country_map.get(value(row, "country"))
            if not iso3:
                continue
            university = value(row, "university")
            external_id = "KF-ACADEMIC-" + hashlib.sha1(f"{iso3}|{university}".encode()).hexdigest()[:16]
            flags = {key: int(str(value(row, key)).strip().casefold() in {"1", "y", "yes", "있음", "o", "true"})
                     for key in ("bachelor", "master", "doctorate", "language_course", "research_center", "sejong_institute", "korea_corner")}
            conn.execute(
                """INSERT OR REPLACE INTO academic_program(external_id, country_iso3, university_name,
                           bachelor, master, doctorate, language_course, research_center,
                           sejong_institute, korea_corner, reference_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (external_id, iso3, university, *(flags[k] for k in flags), date.today().isoformat()),
            )
            count += 1
    conn.commit()
    return count


class KoicaApiClient:
    """Minimal official data.go.kr XML client; the service key is supplied at runtime."""
    BASE_URL = "https://apis.data.go.kr/B260003/BsnsAddService/getBsnsInfoNationList"

    def __init__(self, service_key: str | None = None):
        self.service_key = (service_key or os.getenv("KOICA_SERVICE_KEY", "")).strip()
        if not self.service_key:
            raise RuntimeError("KOICA_SERVICE_KEY is empty. Add the public data portal key to .env.")

    def fetch(self, *, year: int | None = None, rows: int = 1000) -> list[dict[str, str]]:
        params = {"serviceKey": self.service_key, "pageNo": 1, "numOfRows": rows}
        if year is not None:
            params["inqireYear"] = year
        url = self.BASE_URL + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=30) as response:
            root = ET.fromstring(response.read())
        return [{child.tag: child.text or "" for child in item} for item in root.findall(".//item")]
