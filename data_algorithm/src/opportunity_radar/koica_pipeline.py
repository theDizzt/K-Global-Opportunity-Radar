from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from datetime import date, datetime, timezone

from .taxonomy_v2 import classify_sector


BASE_URL = "https://apis.data.go.kr/B260003/BsnsService"
PROJECT_TYPES = ("0102", "07", "09", "04", "12")
TARGET_COUNTRIES = {
    "VNM": {
        "iso2": "VN", "name_ko": "베트남", "name_en": "Vietnam",
        "region_code": "SEA", "aliases": ("베트남", "Vietnam"),
        "nation_codes": ("1775",),
    },
    "IDN": {
        "iso2": "ID", "name_ko": "인도네시아", "name_en": "Indonesia",
        "region_code": "SEA", "aliases": ("인도네시아", "Indonesia"),
        "nation_codes": ("1385",),
    },
    "MNG": {
        "iso2": "MN", "name_ko": "몽골", "name_en": "Mongolia",
        "region_code": "NEA", "aliases": ("몽골", "Mongolia"),
        "nation_codes": ("1514",),
    },
}

KOICA_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestion_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS raw_api_response (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES ingestion_run(id),
    source_type TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    page_no INTEGER,
    fetched_at TEXT NOT NULL,
    http_status INTEGER NOT NULL,
    body TEXT NOT NULL,
    UNIQUE(run_id, request_fingerprint)
);
"""

PROJECT_EXTRA_COLUMNS = {
    "raw_sector_code": "TEXT",
    "raw_sector_name": "TEXT",
    "project_type_code": "TEXT",
    "koica_region_code": "TEXT",
    "koica_region_name": "TEXT",
    "nation_code": "TEXT",
    "description_ko": "TEXT",
    "description_en": "TEXT",
    "purpose_ko": "TEXT",
    "purpose_en": "TEXT",
    "target_area": "TEXT",
    "recipient_name": "TEXT",
    "cooperation_type_code": "TEXT",
    "geo_value": "TEXT",
    "geo_area": "TEXT",
    "detail_status_json": "TEXT",
    "fetched_at": "TEXT",
}


def ensure_koica_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(KOICA_SCHEMA)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(project)")}
    for name, sql_type in PROJECT_EXTRA_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE project ADD COLUMN {name} {sql_type}")
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _item_dict(element: ET.Element | None) -> dict[str, str]:
    if element is None:
        return {}
    return {child.tag.upper(): (child.text or "").strip() for child in element if len(child) == 0}


def _as_int(value: str | None) -> int | None:
    try:
        return int(str(value).strip()) if value not in (None, "") else None
    except ValueError:
        return None


def _as_float(value: str | None) -> float | None:
    try:
        return float(str(value).replace(",", "").strip()) if value not in (None, "") else None
    except ValueError:
        return None


def _country_iso3(name: str, nation_code: str | None = None) -> str | None:
    folded = name.casefold()
    normalized_code = str(nation_code or "").strip()
    for iso3, config in TARGET_COUNTRIES.items():
        if normalized_code and normalized_code in config["nation_codes"]:
            return iso3
        if any(alias.casefold() in folded for alias in config["aliases"]):
            return iso3
    return None


def _sector_code(list_item: dict[str, str], detail: dict[str, str]) -> tuple[str | None, float]:
    raw_sector = list_item.get("SPORT_REALM_NM", "")
    text = " ".join((
        raw_sector,
        list_item.get("BSNS_NM", ""),
        detail.get("KOREAN_BSNS_NM", ""),
        detail.get("BSNS_CN_KOREAN_DC", ""),
        detail.get("BSNS_PURPS_KOREAN_DC", ""),
    ))
    classified, confidence = classify_sector(text)
    if classified:
        return classified, confidence
    direct = {
        "교육": "education",
        "보건의료": "health",
        "농림수산": "climate_agri",
        "기술환경에너지": "climate_agri",
    }
    return direct.get(raw_sector), 0.75 if raw_sector in direct else 0.0


class KoicaAuthorizationError(RuntimeError):
    pass


class KoicaCollector:
    def __init__(
        self,
        conn: sqlite3.Connection,
        service_key: str,
        *,
        transport: Callable[[str], bytes] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
        min_request_interval: float | None = None,
        retry_base_seconds: float = 10.0,
        retry_jitter_seconds: float | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        random_value: Callable[[], float] = random.random,
    ):
        self.conn = conn
        self.service_key = urllib.parse.unquote(service_key.strip())
        if not self.service_key:
            raise ValueError("KOICA service key is empty")
        is_live_transport = transport is None
        self.transport = transport or self._default_transport
        self.sleeper = sleeper
        self.max_retries = max_retries
        self.min_request_interval = (
            5.0
            if min_request_interval is None and is_live_transport
            else float(min_request_interval or 0)
        )
        self.retry_base_seconds = retry_base_seconds
        self.retry_jitter_seconds = 0.75 if retry_jitter_seconds is None and is_live_transport else float(retry_jitter_seconds or 0)
        self.monotonic = monotonic
        self.random_value = random_value
        self._next_request_at = 0.0
        ensure_koica_schema(conn)

    @staticmethod
    def _default_transport(url: str) -> bytes:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "KGlobalOpportunityRadar/0.1",
                "Accept": "application/xml",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise KoicaAuthorizationError(
                    "KOICA API returned HTTP 401: data.go.kr did not recognize KOICA_SERVICE_KEY."
                ) from exc

            if exc.code == 403:
                raise KoicaAuthorizationError(
                    "KOICA API returned HTTP 403: the key is not authorized for API 15158394."
                ) from exc
            raise

    def _wait_for_request_slot(self) -> None:
        delay = self._next_request_at - self.monotonic()
        if delay > 0:
            self.sleeper(delay)

    def _mark_request_complete(self) -> None:
        jitter = self.retry_jitter_seconds * self.random_value()
        self._next_request_at = self.monotonic() + self.min_request_interval + jitter

    def _retry_delay(self, attempt: int, retry_after: str | None = None) -> float:
        delay = self.retry_base_seconds * (2**attempt)
        delay += self.retry_jitter_seconds * self.random_value()
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass
        return delay

    def _call(self, run_id: int, endpoint: str, params: dict[str, object], *, page_no: int | None = None) -> ET.Element:
        safe_params = {k: str(v) for k, v in params.items()}
        query = urllib.parse.urlencode({"serviceKey": self.service_key, **safe_params})
        url = f"{BASE_URL}/{endpoint}?{query}"
        for attempt in range(self.max_retries + 1):
            self._wait_for_request_slot()
            try:
                body = self.transport(url)
                break
            except urllib.error.HTTPError as exc:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= self.max_retries:
                    raise
                delay = self._retry_delay(attempt, retry_after)
                exc.close()
                self.sleeper(delay)
            except (urllib.error.URLError, TimeoutError):
                if attempt >= self.max_retries:
                    raise
                self.sleeper(self._retry_delay(attempt))
            finally:
                self._mark_request_complete()
        fingerprint = hashlib.sha256(
            json.dumps({"endpoint": endpoint, "params": safe_params}, sort_keys=True).encode()
        ).hexdigest()
        self.conn.execute(
            """INSERT OR REPLACE INTO raw_api_response(
                   run_id, source_type, endpoint, request_fingerprint, page_no, fetched_at, http_status, body
               ) VALUES (?, 'KOICA', ?, ?, ?, ?, 200, ?)""",
            (run_id, endpoint, fingerprint, page_no, _now(), body.decode("utf-8", "replace")),
        )
        root = ET.fromstring(body)
        result_code = root.findtext(".//RESULT_CODE")
        if result_code and result_code not in {"00", "0000", "0", "INFO-0"}:
            message = root.findtext(".//RESULT_MSG") or "unknown API error"
            raise RuntimeError(f"KOICA API error {result_code}: {message}")
        return root

    def _list_items(self, run_id: int, year: int, project_type: str, page_size: int) -> Iterable[dict[str, str]]:
        page = 1
        while True:
            root = self._call(
                run_id,
                "getBsnsInfoList",
                {"P_PAGE_NO": page, "P_PAGE_SIZE": page_size, "P_YEAR": year, "P_BSNS_TY_CD": project_type},
                page_no=page,
            )
            items = [_item_dict(item) for item in root.findall(".//ITEM")]
            for item in items:
                yield item
            total = _as_int(root.findtext(".//TOTAL_COUNT"))
            if total is None and items:
                total = _as_int(items[0].get("TOT_CNT"))
            if not items or (total is not None and page * page_size >= total) or len(items) < page_size:
                break
            page += 1

    def _detail(self, run_id: int, project_no: str) -> tuple[dict[str, str], list[str]]:
        root = self._call(run_id, "getBsnsInfoDetail", {"P_BSNS_NO": project_no})
        detail = _item_dict(root.find(".//BODY/ITEM"))
        statuses = [(node.text or "").strip() for node in root.findall(".//PRTN_STTUS") if (node.text or "").strip()]
        return detail, statuses

    def _upsert_countries(self) -> None:
        for iso3, cfg in TARGET_COUNTRIES.items():
            self.conn.execute(
                """INSERT INTO country(iso3, iso2, name_ko, name_en, region_code)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(iso3) DO UPDATE SET iso2=excluded.iso2, name_ko=excluded.name_ko,
                     name_en=excluded.name_en, region_code=excluded.region_code""",
                (iso3, cfg["iso2"], cfg["name_ko"], cfg["name_en"], cfg["region_code"]),
            )

    def _upsert_project(self, list_item: dict[str, str], detail: dict[str, str], statuses: list[str]) -> str:
        country_name = list_item.get("NATION_NM") or detail.get("RECIPCONTY_NM", "")
        iso3 = _country_iso3(country_name, list_item.get("NATION_CD"))
        if not iso3:
            raise ValueError(f"Unsupported target country: {country_name}")
        project_no = list_item.get("BSNS_NO") or detail.get("BSNS_NO")
        if not project_no:
            raise ValueError("KOICA project is missing BSNS_NO")
        name = list_item.get("BSNS_NM") or detail.get("KOREAN_BSNS_NM") or project_no
        sector, confidence = _sector_code(list_item, detail)
        fetched_at = _now()
        merged = {"list": list_item, "detail": detail, "statuses": statuses}
        body = "\n".join(filter(None, (
            detail.get("BSNS_PURPS_KOREAN_DC"), detail.get("BSNS_CN_KOREAN_DC"),
            detail.get("BSNS_PURPS_ENG_DC"), detail.get("BSNS_CN_ENG_DC"),
        )))
        external_id = f"KOICA-BSNS-{project_no}"
        self.conn.execute(
            """INSERT INTO source_record(source_type, external_id, country_iso3, title, body,
                       published_at, source_url, raw_json)
               VALUES ('KOICA', ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_type, external_id) DO UPDATE SET
                 country_iso3=excluded.country_iso3, title=excluded.title, body=excluded.body,
                 published_at=excluded.published_at, source_url=excluded.source_url, raw_json=excluded.raw_json""",
            (external_id, iso3, name, body, f"{list_item.get('BSNS_BEGIN_YEAR')}-01-01" if list_item.get("BSNS_BEGIN_YEAR") else None,
             "https://www.data.go.kr/data/15158394/openapi.do", json.dumps(merged, ensure_ascii=False)),
        )
        source_record_id = self.conn.execute(
            "SELECT id FROM source_record WHERE source_type='KOICA' AND external_id=?", (external_id,)
        ).fetchone()[0]
        status_text = " | ".join(statuses)
        values = (
            source_record_id, external_id, iso3, sector, name,
            _as_int(list_item.get("BSNS_BEGIN_YEAR")), _as_int(list_item.get("BSNS_END_YEAR")),
            _as_float(detail.get("BSNS_BUDGET_DOLLAR_AMOUNT")), status_text, detail.get("REOF_NM"), confidence,
            list_item.get("SPORT_REALM_CD"), list_item.get("SPORT_REALM_NM"), list_item.get("BSNS_TY_CD"),
            list_item.get("KOICA_AREA_SE_CD"), list_item.get("KOICA_AREA_SE_NM"), list_item.get("NATION_CD"),
            detail.get("BSNS_CN_KOREAN_DC"), detail.get("BSNS_CN_ENG_DC"), detail.get("BSNS_PURPS_KOREAN_DC"),
            detail.get("BSNS_PURPS_ENG_DC"), detail.get("BSNS_TRGET_AREA_NM"), detail.get("RECIPCONTY_NM"),
            detail.get("CPRBIZ_SE_CD"), detail.get("LA_LO_VALUE"), detail.get("LA_LO_VALUE_AREA"),
            json.dumps(statuses, ensure_ascii=False), fetched_at,
        )
        self.conn.execute(
            """INSERT INTO project(
                   source_record_id, external_id, country_iso3, sector_code, name, start_year, end_year,
                   budget, status, agency, classification_confidence, raw_sector_code, raw_sector_name,
                   project_type_code, koica_region_code, koica_region_name, nation_code, description_ko,
                   description_en, purpose_ko, purpose_en, target_area, recipient_name,
                   cooperation_type_code, geo_value, geo_area, detail_status_json, fetched_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(external_id) DO UPDATE SET
                 source_record_id=excluded.source_record_id, country_iso3=excluded.country_iso3,
                 sector_code=excluded.sector_code, name=excluded.name, start_year=excluded.start_year,
                 end_year=excluded.end_year, budget=excluded.budget, status=excluded.status,
                 agency=excluded.agency, classification_confidence=excluded.classification_confidence,
                 raw_sector_code=excluded.raw_sector_code, raw_sector_name=excluded.raw_sector_name,
                 project_type_code=excluded.project_type_code, koica_region_code=excluded.koica_region_code,
                 koica_region_name=excluded.koica_region_name, nation_code=excluded.nation_code,
                 description_ko=excluded.description_ko, description_en=excluded.description_en,
                 purpose_ko=excluded.purpose_ko, purpose_en=excluded.purpose_en,
                 target_area=excluded.target_area, recipient_name=excluded.recipient_name,
                 cooperation_type_code=excluded.cooperation_type_code, geo_value=excluded.geo_value,
                 geo_area=excluded.geo_area, detail_status_json=excluded.detail_status_json,
                 fetched_at=excluded.fetched_at""",
            values,
        )
        return iso3

    def collect(
        self,
        *,
        years: Iterable[int] = range(1991, date.today().year + 1),
        project_types: Iterable[str] = PROJECT_TYPES,
        page_size: int = 10,
    ) -> dict[str, int]:
        years = tuple(years)
        project_types = tuple(project_types)
        self._upsert_countries()
        cursor = self.conn.execute(
            "INSERT INTO ingestion_run(source_type, started_at, status, parameters_json) VALUES ('KOICA', ?, 'running', ?)",
            (_now(), json.dumps({"years": years, "project_types": project_types, "page_size": page_size})),
        )
        run_id = cursor.lastrowid
        counts = {iso3: 0 for iso3 in TARGET_COUNTRIES}
        seen: set[str] = set()
        errors: list[dict[str, object]] = []
        try:
            for year in years:
                for project_type in project_types:
                    for item in self._list_items(run_id, year, project_type, page_size):
                        iso3 = _country_iso3(
                            item.get("NATION_NM", ""),
                            item.get("NATION_CD"),
                        )
                        project_no = item.get("BSNS_NO", "")
                        if not iso3 or not project_no or project_no in seen:
                            continue
                        detail, statuses = self._detail(run_id, project_no)
                        stored_country = self._upsert_project(item, detail, statuses)
                        seen.add(project_no)
                        counts[stored_country] += 1
                        self.conn.commit()
            observed_at = date.today().isoformat()
            for iso3, count in counts.items():
                self.conn.execute(
                    """INSERT INTO source_coverage(country_iso3, source_type, observed_at, record_count)
                       VALUES (?, 'KOICA', ?, ?)
                       ON CONFLICT(country_iso3, source_type) DO UPDATE SET
                         observed_at=excluded.observed_at, record_count=excluded.record_count""",
                    (iso3, observed_at, count),
                )
            self.conn.execute(
                "UPDATE ingestion_run SET finished_at=?, status='complete', record_count=? WHERE id=?",
                (_now(), sum(counts.values()), run_id),
            )
            self.conn.commit()
            return counts
        except Exception as exc:
            self.conn.execute(
                "UPDATE ingestion_run SET finished_at=?, status='failed', error_message=? WHERE id=?",
                (_now(), str(exc)[:1000], run_id),
            )
            self.conn.commit()
            raise
