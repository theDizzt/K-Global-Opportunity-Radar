from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import date

from .multisector import classify_sectors
from .taxonomy_v2 import SECTORS


STANDARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS country_alias (
    alias_key TEXT PRIMARY KEY,
    alias TEXT NOT NULL,
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    language TEXT,
    source_type TEXT NOT NULL DEFAULT 'COMMON',
    is_preferred INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sector_mapping (
    source_type TEXT NOT NULL,
    raw_value TEXT NOT NULL,
    sector_code TEXT NOT NULL REFERENCES sector(code),
    mapping_method TEXT NOT NULL,
    confidence REAL NOT NULL,
    notes TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(source_type, raw_value)
);

CREATE TABLE IF NOT EXISTS source_catalog (
    source_code TEXT PRIMARY KEY,
    provider_name TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    access_method TEXT NOT NULL,
    endpoint_url TEXT,
    landing_url TEXT NOT NULL,
    update_cycle TEXT,
    usage_status TEXT NOT NULL,
    terms_note TEXT,
    checked_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS record_sector (
    source_record_id INTEGER NOT NULL REFERENCES source_record(id) ON DELETE CASCADE,
    sector_code TEXT NOT NULL REFERENCES sector(code),
    confidence REAL NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    mapping_method TEXT NOT NULL,
    PRIMARY KEY(source_record_id, sector_code)
);

CREATE TABLE IF NOT EXISTS record_lineage (
    source_record_id INTEGER PRIMARY KEY REFERENCES source_record(id) ON DELETE CASCADE,
    ingestion_run_id INTEGER REFERENCES ingestion_run(id),
    raw_response_id INTEGER REFERENCES raw_api_response(id),
    provider_name TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    reference_date TEXT,
    date_precision TEXT NOT NULL DEFAULT 'unknown',
    transformation_version TEXT NOT NULL,
    quality_status TEXT NOT NULL DEFAULT 'unreviewed'
);

CREATE TABLE IF NOT EXISTS data_quality_issue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    external_id TEXT,
    source_record_id INTEGER REFERENCES source_record(id),
    issue_type TEXT NOT NULL,
    field_name TEXT,
    raw_value TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    detected_at TEXT NOT NULL,
    resolution_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_country_alias_iso3 ON country_alias(country_iso3);
CREATE INDEX IF NOT EXISTS idx_quality_status ON data_quality_issue(status, issue_type);
"""


COUNTRY_ALIASES = {
    "VNM": (
        ("베트남", "ko", 1), ("Vietnam", "en", 1), ("Viet Nam", "en", 0),
        ("VietNam", "en", 0), ("Việt Nam", "vi", 0),
        ("Socialist Republic of Viet Nam", "en", 0),
    ),
    "IDN": (
        ("인도네시아", "ko", 1), ("Indonesia", "en", 1),
        ("Republic of Indonesia", "en", 0), ("Republik Indonesia", "id", 0),
    ),
    "MNG": (
        ("몽골", "ko", 1), ("Mongolia", "en", 1),
        ("Монгол Улс", "mn", 0), ("Mongol Uls", "mn", 0),
    ),
}


COUNTRY_MASTER = {
    "VNM": ("VN", "\ubca0\ud2b8\ub0a8", "Vietnam", "SEA"),
    "IDN": ("ID", "\uc778\ub3c4\ub124\uc2dc\uc544", "Indonesia", "SEA"),
    "MNG": ("MN", "\ubabd\uace8", "Mongolia", "NEA"),
}

SOURCE_CATALOG = (
    ("KOICA_PROJECT", "한국국제협력단", "사업정보조회", "data.go.kr REST API",
     "https://apis.data.go.kr/B260003/BsnsService", "https://www.data.go.kr/data/15158394/openapi.do",
     "실시간", "approved", "공공데이터포털 승인키 사용"),
    ("KF_BUSINESS", "한국국제교류재단", "공공외교 사업 정보", "data.go.kr REST API",
     "https://apis.data.go.kr/B260004/PublicDiplomacyBusinessInfoService/getPublicDiplomacyBusinessInfoList",
     "https://www.data.go.kr/data/15099202/openapi.do", "실시간", "approved", "공공데이터포털 이용조건 적용"),
    ("KF_ORG", "한국국제교류재단", "공공외교 수혜·참여기관", "data.go.kr REST API",
     "https://apis.data.go.kr/B260004/PublicDiplomacyOrgService/getPublicDiplomacyOrgList",
     "https://www.data.go.kr/data/15099204/openapi.do", "실시간", "approved", "공공데이터포털 이용조건 적용"),
    ("KF_RESULTS", "한국국제교류재단", "공공외교 사업별 실적", "data.go.kr REST API",
     "https://apis.data.go.kr/B260004/PublicDiplomacyBusinessResultsService/getPublicDiplomacyBusinessResultsList",
     "https://www.data.go.kr/data/15112896/openapi.do", "실시간", "approved", "공공데이터포털 이용조건 적용"),
    ("KF_STUDIES", "한국국제교류재단", "해외대학 한국학 현황", "official Excel download",
     None, "https://www.kf.or.kr/koreanstudies/koreaStudiesList.do", "수시", "manual_download",
     "인용 시 한국국제교류재단 제공 자료임을 명시; 2016~17 전수조사 기반이며 시차 주의"),
    ("MOFA_RELATION", "외교부", "국가·지역별 우리나라와의 관계", "data.go.kr REST API",
     "https://apis.data.go.kr/1262000/OverviewKorRelationService/getOverviewKorRelationList",
     "https://www.data.go.kr/data/15099539/openapi.do", "실시간", "approved", "공공데이터포털 이용조건 적용"),
    ("MOFA_ECONOMY", "외교부", "국가·지역별 경제현황", "data.go.kr REST API",
     "https://apis.data.go.kr/1262000/OverviewEconomicService/OverviewEconomicList",
     "https://www.data.go.kr/data/15099538/openapi.do", "실시간", "approved", "공공데이터포털 이용조건 적용"),
    ("MOFA_WARNING", "외교부", "국가·지역별 여행경보", "data.go.kr REST API",
     "https://apis.data.go.kr/1262000/TravelWarningServiceV3/getTravelWarningListV3",
     "https://www.data.go.kr/data/15000827/openapi.do", "실시간", "approved", "공공데이터포털 이용조건 적용"),
    ("MOFA_LOD", "외교부", "보도자료·브리핑·발간자료 LOD", "SPARQL",
     "http://opendata.mofa.go.kr/{dataset}/sparql", "https://opendata.mofa.go.kr/lod/introduce.do",
     "데이터셋별 상이", "approved", "공공데이터법에 따라 LOD로 개방; 원문 URI 보존"),
    ("MOFA_INSIGHT", "외교부", "MOFA 인사이트", "website/reference only", None,
     "https://insight.mofa.go.kr/", "수시", "reference_only",
     "별도 공개 API·재이용 약관 확인 전 화면 자동수집 금지; underlying LOD/API 우선 사용"),
    ("OECD_CRS", "OECD", "Creditor Reporting System activity-level data",
     "official bulk text/parquet download", None,
     "https://data-explorer.oecd.org/vis?df%5Bag%5D=OECD.DCD.FSD&df%5Bid%5D=DSD_CRS%40DF_CRS",
     "연간", "approved",
     "한국 공여 활동을 필터링해 KOICA 누락 교차검증 및 장기 사업 라벨로 사용"),
)


def normalize_country_alias(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().strip()
    return re.sub(r"[^0-9a-z가-힣]+", "", value)


def ensure_standard_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(STANDARD_SCHEMA)
    today = date.today().isoformat()
    for iso3, (iso2, name_ko, name_en, region_code) in COUNTRY_MASTER.items():
        conn.execute(
            """INSERT INTO country(iso3, iso2, name_ko, name_en, region_code)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(iso3) DO UPDATE SET iso2=excluded.iso2,
                 name_ko=excluded.name_ko, name_en=excluded.name_en,
                 region_code=excluded.region_code""",
            (iso3, iso2, name_ko, name_en, region_code),
        )

    for iso3, aliases in COUNTRY_ALIASES.items():
        for alias, language, preferred in aliases:
            conn.execute(
                """INSERT INTO country_alias(alias_key, alias, country_iso3, language, source_type, is_preferred)
                   VALUES (?, ?, ?, ?, 'COMMON', ?)
                   ON CONFLICT(alias_key) DO UPDATE SET alias=excluded.alias,
                     country_iso3=excluded.country_iso3, language=excluded.language,
                     is_preferred=excluded.is_preferred""",
                (normalize_country_alias(alias), alias, iso3, language, preferred),
            )
    for row in SOURCE_CATALOG:
        conn.execute(
            """INSERT INTO source_catalog(source_code, provider_name, dataset_name, access_method,
                       endpoint_url, landing_url, update_cycle, usage_status, terms_note, checked_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_code) DO UPDATE SET provider_name=excluded.provider_name,
                 dataset_name=excluded.dataset_name, access_method=excluded.access_method,
                 endpoint_url=excluded.endpoint_url, landing_url=excluded.landing_url,
                 update_cycle=excluded.update_cycle, usage_status=excluded.usage_status,
                 terms_note=excluded.terms_note, checked_at=excluded.checked_at""",
            (*row, today),
        )


def resolve_country_iso3(conn: sqlite3.Connection, value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    upper = raw.upper()
    row = conn.execute("SELECT iso3 FROM country WHERE iso3=? OR iso2=?", (upper, upper)).fetchone()
    if row:
        return row[0]
    row = conn.execute(
        "SELECT country_iso3 FROM country_alias WHERE alias_key=?",
        (normalize_country_alias(raw),),
    ).fetchone()
    return row[0] if row else None


def record_quality_issue(
    conn: sqlite3.Connection, *, source_type: str, issue_type: str,
    external_id: str | None = None, source_record_id: int | None = None,
    field_name: str | None = None, raw_value: object = None,
) -> None:
    conn.execute(
        """INSERT INTO data_quality_issue(source_type, external_id, source_record_id,
                   issue_type, field_name, raw_value, detected_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (source_type, external_id, source_record_id, issue_type, field_name,
         None if raw_value is None else str(raw_value), date.today().isoformat()),
    )
