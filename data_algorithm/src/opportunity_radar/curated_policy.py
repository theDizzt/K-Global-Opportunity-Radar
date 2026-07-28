from __future__ import annotations

import json
import re
import sqlite3
import urllib.parse
from pathlib import Path

from .ingest import _source_record
from .statistical_signals import TIER_BY_EVENT, sync_signal_events
from .taxonomy_v2 import SECTORS


OFFICIAL_HOST_SUFFIXES = (
    "mofa.go.kr",
    "koica.go.kr",
    "odakorea.go.kr",
)


def _official_source_url(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").casefold()
    return any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in OFFICIAL_HOST_SUFFIXES
    )


def load_curated_policy_evidence(
    conn: sqlite3.Connection,
    path: str | Path,
) -> dict[str, object]:
    """Load source-verified Tier A/B policy actions with strict lineage."""
    source_path = Path(path)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("Curated policy file must contain a records list")

    source_records = 0
    evidence_rows = 0
    countries: set[str] = set()
    sectors_seen: set[str] = set()
    for item in records:
        required = {
            "external_id",
            "country_iso3",
            "title",
            "event_date",
            "event_type",
            "sectors",
            "organizations",
            "supporting_text",
            "source_url",
        }
        missing = sorted(required - set(item))
        if missing:
            raise ValueError(
                f"Policy record is missing fields: {', '.join(missing)}"
            )
        country = str(item["country_iso3"]).upper()
        if not conn.execute(
            "SELECT EXISTS(SELECT 1 FROM country WHERE iso3=?)",
            (country,),
        ).fetchone()[0]:
            raise ValueError(f"Unknown country in policy record: {country}")
        event_type = str(item["event_type"])
        if TIER_BY_EVENT.get(event_type) not in {"A", "B"}:
            raise ValueError(
                f"Curated event_type must be Tier A/B: {event_type}"
            )
        event_date = str(item["event_date"])
        if not re.fullmatch(r"(?:19|20)\d{2}-\d{2}-\d{2}", event_date):
            raise ValueError(f"Invalid policy event_date: {event_date}")
        source_url = str(item["source_url"])
        if not _official_source_url(source_url):
            raise ValueError(
                f"Policy evidence URL is not an allowed official host: {source_url}"
            )
        sectors = [str(value) for value in item["sectors"]]
        unknown_sectors = sorted(set(sectors) - set(SECTORS))
        if unknown_sectors:
            raise ValueError(
                "Unknown policy sectors: " + ", ".join(unknown_sectors)
            )
        organizations = [
            str(value).strip()
            for value in item["organizations"]
            if str(value).strip()
        ]
        source_type = str(item.get("source_type") or "MOFA")
        raw = {
            **item,
            "curation_method": "source_verified_official_document",
            "curated_from": source_path.name,
        }
        record_id = _source_record(
            conn,
            source=source_type,
            external_id=str(item["external_id"]),
            country=country,
            title=str(item["title"]),
            body=str(item["supporting_text"]),
            published_at=event_date,
            url=source_url,
            raw=raw,
        )
        source_records += 1
        for sector in sectors:
            conn.execute(
                """INSERT INTO evidence(
                       source_record_id, country_iso3, sector_code, event_type,
                       event_date, organizations_json, confidence,
                       supporting_text
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(source_record_id, sector_code, event_type)
                   DO UPDATE SET
                     country_iso3=excluded.country_iso3,
                     event_date=excluded.event_date,
                     organizations_json=excluded.organizations_json,
                     confidence=excluded.confidence,
                     supporting_text=excluded.supporting_text""",
                (
                    record_id,
                    country,
                    sector,
                    event_type,
                    event_date,
                    json.dumps(organizations, ensure_ascii=False),
                    float(item.get("confidence", 1.0)),
                    str(item["supporting_text"]),
                ),
            )
            evidence_rows += 1
            sectors_seen.add(sector)
        countries.add(country)
    conn.commit()
    signal_stats = sync_signal_events(conn)
    return {
        "source_file": str(source_path),
        "source_records_upserted": source_records,
        "evidence_rows_upserted": evidence_rows,
        "countries": sorted(countries),
        "sectors": sorted(sectors_seen),
        "signal_sync": signal_stats,
    }
