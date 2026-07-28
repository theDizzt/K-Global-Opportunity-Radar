from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date

from .countries import TARGET_COUNTRIES, upsert_target_countries
from .taxonomy_v2 import classify_sector
from .ingest import _coverage, _source_record
from .public_api import DataGoKrClient, IngestionRun


# 1. KF 공공외교 사업·기관·실적 공식 API 주소
KF_ENDPOINTS = {
    "business": "https://apis.data.go.kr/B260004/PublicDiplomacyBusinessInfoService/getPublicDiplomacyBusinessInfoList",
    "organization": "https://apis.data.go.kr/B260004/PublicDiplomacyOrgService/getPublicDiplomacyOrgList",
    "results": "https://apis.data.go.kr/B260004/PublicDiplomacyBusinessResultsService/getPublicDiplomacyBusinessResultsList",
}

# 2. 화면과 보고서에 연결할 공공데이터포털 원문 페이지
KF_SOURCE_URLS = {
    "business": "https://www.data.go.kr/data/15099202/openapi.do",
    "organization": "https://www.data.go.kr/data/15099204/openapi.do",
    "results": "https://www.data.go.kr/data/15112896/openapi.do",
}

# 3. 국가별 KF 협력기관을 저장하는 확장 스키마
KF_SCHEMA = """
CREATE TABLE IF NOT EXISTS kf_partner_org (
    external_id TEXT PRIMARY KEY,
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    name_ko TEXT NOT NULL,
    name_en TEXT,
    benefit_count INTEGER,
    homepage TEXT,
    fetched_at TEXT NOT NULL
);
"""


# 4. 원본에 고정 ID가 없을 때 중복 방지용 안정 해시 생성
def _stable_id(prefix: str, *values: object) -> str:
    raw = "|".join("" if value is None else str(value).strip() for value in values)
    return f"{prefix}-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]}"


# 5. 연도 값만 제공되는 자료를 해당 연도 1월 1일로 표준화
def _year_date(value: object) -> str | None:
    try:
        return f"{int(value):04d}-01-01"
    except (TypeError, ValueError):
        return None


# 6. KF API 자료를 원문·기관·분야 근거 테이블로 적재
class KfCollector:
    def __init__(self, conn: sqlite3.Connection, service_key: str, **client_options):
        self.conn = conn
        self.client = DataGoKrClient(conn, service_key, **client_options)
        conn.executescript(KF_SCHEMA)
        conn.commit()

    def _add_evidence(
        self,
        record_id: int,
        iso3: str,
        item: dict,
        *,
        event_type: str,
        organizations: list[str],
    ) -> bool:
        # 사업명·목적·기관명을 함께 분류해 국가×분야 근거를 생성합니다.
        text = "\n".join(
            str(item.get(key) or "")
            for key in (
                "kor_business_nm", "eng_business_nm", "business_purpose",
                "unit_business", "detail_business", "org_nm",
            )
        )
        sector, confidence = classify_sector(text)
        if not sector:
            return False
        self.conn.execute(
            """INSERT INTO evidence(source_record_id, country_iso3, sector_code,
                       event_type, event_date, organizations_json, confidence, supporting_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_record_id, sector_code, event_type) DO UPDATE SET
                 event_date=excluded.event_date,
                 organizations_json=excluded.organizations_json,
                 confidence=excluded.confidence,
                 supporting_text=excluded.supporting_text""",
            (
                record_id, iso3, sector, event_type, _year_date(item.get("business_year")),
                json.dumps([x for x in organizations if x], ensure_ascii=False),
                min(0.95, confidence * 0.95), text[:4000],
            ),
        )
        return True

    def _store_business(self, iso3: str, item: dict) -> None:
        external_id = _stable_id(
            "KF-BUS", iso3, item.get("business_year"), item.get("kor_business_nm"),
            item.get("unit_business"), item.get("detail_business"),
        )
        title = item.get("kor_business_nm") or item.get("eng_business_nm") or external_id
        body = "\n".join(
            str(item.get(key) or "")
            for key in ("business_purpose", "business_target", "unit_business", "detail_business")
            if item.get(key)
        )
        record_id = _source_record(
            self.conn, source="KF", external_id=external_id, country=iso3,
            title=title, body=body, published_at=_year_date(item.get("business_year")),
            url=KF_SOURCE_URLS["business"], raw=item,
        )
        self._add_evidence(record_id, iso3, item, event_type="joint_project", organizations=["한국국제교류재단"])

    def _store_result(self, iso3: str, item: dict) -> None:
        external_id = _stable_id(
            "KF-RESULT", iso3, item.get("business_year"), item.get("kor_business_nm"),
            item.get("org_nm"), item.get("business_degree"),
        )
        title = item.get("kor_business_nm") or item.get("eng_business_nm") or external_id
        record_id = _source_record(
            self.conn, source="KF", external_id=external_id, country=iso3,
            title=title, body=str(item.get("org_nm") or ""),
            published_at=_year_date(item.get("business_year")),
            url=KF_SOURCE_URLS["results"], raw=item,
        )
        self._add_evidence(
            record_id, iso3, item, event_type="joint_project",
            organizations=["한국국제교류재단", str(item.get("org_nm") or "")],
        )

    def _store_organization(self, iso3: str, item: dict) -> None:
        external_id = _stable_id(
            "KF-ORG", iso3, item.get("kor_org_nm"), item.get("eng_org_nm"), item.get("homepage")
        )
        name = item.get("kor_org_nm") or item.get("eng_org_nm") or external_id
        self.conn.execute(
            """INSERT INTO kf_partner_org(external_id, country_iso3, name_ko, name_en,
                       benefit_count, homepage, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(external_id) DO UPDATE SET
                 benefit_count=excluded.benefit_count, homepage=excluded.homepage,
                 fetched_at=excluded.fetched_at""",
            (
                external_id, iso3, name, item.get("eng_org_nm"), item.get("benefit_cnt"),
                item.get("homepage"), date.today().isoformat(),
            ),
        )
        _source_record(
            self.conn, source="KF", external_id=external_id, country=iso3,
            title=name, body=f"수혜·참여 실적: {item.get('benefit_cnt') or 0}",
            url=KF_SOURCE_URLS["organization"], raw=item,
        )

    def collect(self, *, page_size: int = 1000, max_pages: int | None = None) -> dict[str, int]:
        # 시범국 ISO2 조건으로 세 API를 순회하고 국가별 수집 건수를 기록합니다.
        upsert_target_countries(self.conn)
        run = IngestionRun(self.conn, "KF", {"countries": list(TARGET_COUNTRIES), "page_size": page_size})
        counts = {iso3: 0 for iso3 in TARGET_COUNTRIES}
        try:
            for iso3, cfg in TARGET_COUNTRIES.items():
                params = {"cond[country_iso_alp2::EQ]": cfg["iso2"]}
                for kind, endpoint in KF_ENDPOINTS.items():
                    for item in self.client.pages(
                        run.id, "KF", endpoint, params, page_size=page_size, max_pages=max_pages
                    ):
                        if item.get("country_iso_alp2") not in {None, "", cfg["iso2"]}:
                            continue
                        if kind == "business":
                            self._store_business(iso3, item)
                        elif kind == "organization":
                            self._store_organization(iso3, item)
                        else:
                            self._store_result(iso3, item)
                        counts[iso3] += 1
                _coverage(self.conn, iso3, "KF", counts[iso3], date.today().isoformat())
                self.conn.commit()
            run.complete(sum(counts.values()))
            return counts
        except Exception as exc:
            run.fail(exc)
            raise
