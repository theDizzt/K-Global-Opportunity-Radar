from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date

from .taxonomy_v2 import classify_sector
from .countries import TARGET_COUNTRIES, upsert_target_countries
from .ingest import _coverage, _source_record
from .public_api import DataGoKrClient, IngestionRun


MOFA_ENDPOINTS = {
    "relation": "https://apis.data.go.kr/1262000/OverviewKorRelationService/getOverviewKorRelationList",
    "economy": "https://apis.data.go.kr/1262000/OverviewEconomicService/OverviewEconomicList",
    "warning": "https://apis.data.go.kr/1262000/TravelWarningServiceV3/getTravelWarningListV3",
}

MOFA_SOURCE_URLS = {
    "relation": "https://www.data.go.kr/data/15099539/openapi.do",
    "economy": "https://www.data.go.kr/data/15099538/openapi.do",
    "warning": "https://www.data.go.kr/data/15000827/openapi.do",
}

MOFA_SCHEMA = """
CREATE TABLE IF NOT EXISTS country_profile (
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    profile_type TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    gdp REAL,
    gdp_per_capita REAL,
    gdp_growth_rate REAL,
    inflation_rate REAL,
    unemployment_rate REAL,
    export_amount REAL,
    import_amount REAL,
    major_industry TEXT,
    main_resource TEXT,
    data_json TEXT NOT NULL,
    PRIMARY KEY(country_iso3, profile_type)
);
"""


def _number(value: object) -> float | None:
    try:
        return float(str(value).replace(",", "").strip()) if value not in {None, ""} else None
    except (TypeError, ValueError):
        return None


def _warning_level(item: dict) -> int:
    if item.get("ban_yna") or item.get("ban_yn_partial"):
        return 4
    if item.get("control") or item.get("control_partial"):
        return 3
    if item.get("limita") or item.get("limita_partial"):
        return 2
    if item.get("attention") or item.get("attention_partial"):
        return 1
    return 0


class MofaCollector:
    def __init__(self, conn: sqlite3.Connection, service_key: str, **client_options):
        self.conn = conn
        self.client = DataGoKrClient(conn, service_key, **client_options)
        conn.executescript(MOFA_SCHEMA)
        conn.commit()

    def _store_profile(self, iso3: str, profile_type: str, item: dict) -> None:
        observed_at = date.today().isoformat()
        self.conn.execute(
            """INSERT INTO country_profile(
                   country_iso3, profile_type, observed_at, gdp, gdp_per_capita,
                   gdp_growth_rate, inflation_rate, unemployment_rate, export_amount,
                   import_amount, major_industry, main_resource, data_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(country_iso3, profile_type) DO UPDATE SET
                 observed_at=excluded.observed_at, gdp=excluded.gdp,
                 gdp_per_capita=excluded.gdp_per_capita,
                 gdp_growth_rate=excluded.gdp_growth_rate,
                 inflation_rate=excluded.inflation_rate,
                 unemployment_rate=excluded.unemployment_rate,
                 export_amount=excluded.export_amount, import_amount=excluded.import_amount,
                 major_industry=excluded.major_industry, main_resource=excluded.main_resource,
                 data_json=excluded.data_json""",
            (
                iso3, profile_type, observed_at, _number(item.get("gdp")),
                _number(item.get("gdp_per_capita")), _number(item.get("gdp_growth_rate")),
                _number(item.get("inflation_rate")), _number(item.get("unemployment_rate")),
                _number(item.get("export_amount")), _number(item.get("import_amount")),
                item.get("major_industry"), item.get("main_resource"),
                json.dumps(item, ensure_ascii=False),
            ),
        )
        title = f"{item.get('country_nm') or TARGET_COUNTRIES[iso3]['name_ko']} {profile_type} 현황"
        body = "\n".join(str(value) for value in item.values() if value not in {None, ""})
        external_id = f"MOFA-{profile_type.upper()}-{iso3}"
        record_id = _source_record(
            self.conn, source="MOFA", external_id=external_id, country=iso3,
            title=title, body=body, published_at=observed_at,
            url=MOFA_SOURCE_URLS[profile_type], raw=item,
        )
        if profile_type == "relation":
            sector, confidence = classify_sector(body)
            if sector:
                self.conn.execute(
                    """INSERT INTO evidence(source_record_id, country_iso3, sector_code,
                               event_type, event_date, organizations_json, confidence, supporting_text)
                       VALUES (?, ?, ?, 'agreement', ?, '[]', ?, ?)
                       ON CONFLICT(source_record_id, sector_code, event_type) DO UPDATE SET
                         event_date=excluded.event_date, confidence=excluded.confidence,
                         supporting_text=excluded.supporting_text""",
                    (record_id, iso3, sector, observed_at, min(0.85, confidence * 0.9), body[:4000]),
                )

    def _store_warning(self, iso3: str, item: dict) -> None:
        level = _warning_level(item)
        labels = [
            str(item.get(key)) for key in ("attention", "limita", "control", "ban_yna") if item.get(key)
        ]
        title = f"{item.get('country_name') or TARGET_COUNTRIES[iso3]['name_ko']} 여행경보"
        if labels:
            title += ": " + ", ".join(labels)
        published_at = str(item.get("wrt_dt") or date.today().isoformat())
        raw_id = str(item.get("id") or hashlib.sha1(json.dumps(item, sort_keys=True).encode()).hexdigest()[:12])
        self.conn.execute(
            """INSERT INTO safety_notice(external_id, country_iso3, warning_level,
                       published_at, title, source_url)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(external_id) DO UPDATE SET warning_level=excluded.warning_level,
                 published_at=excluded.published_at, title=excluded.title,
                 source_url=excluded.source_url""",
            (f"MOFA-WARNING-{iso3}-{raw_id}", iso3, level, published_at, title, MOFA_SOURCE_URLS["warning"]),
        )

    def collect(self, *, page_size: int = 200, max_pages: int | None = None) -> dict[str, int]:
        upsert_target_countries(self.conn)
        run = IngestionRun(self.conn, "MOFA", {"countries": list(TARGET_COUNTRIES), "page_size": page_size})
        counts = {iso3: 0 for iso3 in TARGET_COUNTRIES}
        try:
            for iso3, cfg in TARGET_COUNTRIES.items():
                params = {"cond[country_iso_alp2::EQ]": cfg["iso2"]}
                for profile_type in ("relation", "economy"):
                    for item in self.client.pages(
                        run.id, "MOFA", MOFA_ENDPOINTS[profile_type], params,
                        page_size=page_size, max_pages=max_pages,
                    ):
                        if item.get("country_iso_alp2") not in {None, "", cfg["iso2"]}:
                            continue
                        self._store_profile(iso3, profile_type, item)
                        counts[iso3] += 1

            # TravelWarningServiceV3 uses ISO3 in the response and rejects the
            # ISO2 condition used by the overview services, so fetch it once.
            for item in self.client.pages(
                run.id, "MOFA", MOFA_ENDPOINTS["warning"], {},
                page_size=max(page_size, 200), max_pages=max_pages,
            ):
                iso3 = str(item.get("iso_code") or "").upper()
                if iso3 in counts:
                    self._store_warning(iso3, item)
                    counts[iso3] += 1

            for iso3, count in counts.items():
                _coverage(self.conn, iso3, "MOFA", count, date.today().isoformat())
            run.complete(sum(counts.values()))
            return counts
        except Exception as exc:
            run.fail(exc)
            raise
