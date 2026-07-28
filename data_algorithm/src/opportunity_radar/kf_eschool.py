from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.request
from collections.abc import Callable
from datetime import date
from html.parser import HTMLParser

from .countries import TARGET_COUNTRIES, upsert_target_countries
from .ingest import _coverage, _source_record
from .public_api import IngestionRun, now_utc


# 1. 한국국제교류재단 글로벌 e-스쿨 공식 공개 페이지와 구조화 저장 스키마
KF_ESCHOOL_URL = "https://www.kf.or.kr/koreanstudies/globalESchoolList.do"
KF_ESCHOOL_SCHEMA = """
CREATE TABLE IF NOT EXISTS kf_eschool_course (
    external_id TEXT PRIMARY KEY,
    source_record_id INTEGER NOT NULL REFERENCES source_record(id),
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    business_year INTEGER,
    business_type TEXT,
    sending_university TEXT,
    study_type TEXT,
    course_title TEXT NOT NULL,
    semester TEXT,
    receiving_university TEXT,
    student_count INTEGER,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kf_eschool_country_year
    ON kf_eschool_course(country_iso3, business_year);
"""


# 2. 화면의 결과 표 중 실제 강좌 행만 추출하는 HTML 파서
class _GlobalESchoolParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._inside_result_body = False
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if tag == "tbody" and attributes.get("id") == "globalEschoolList":
            self._inside_result_body = True
        elif tag == "tr" and self._inside_result_body:
            self._row = []
        elif tag == "td" and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag == "tbody" and self._inside_result_body:
            self._inside_result_body = False


# 3. 국가명과 숫자를 DB 표준 형식으로 변환
def _target_country_iso3(country_name: str) -> str | None:
    normalized = country_name.strip().casefold()
    for iso3, config in TARGET_COUNTRIES.items():
        if normalized in {alias.casefold() for alias in config["aliases"]}:
            return iso3
    return None


def _optional_int(value: str) -> int | None:
    try:
        return int(value.replace(",", "").strip())
    except (AttributeError, TypeError, ValueError):
        return None


# 4. KF 공식 페이지를 내려받고 원문 응답을 수집 이력에 보존
def _default_transport(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "K-Global-Opportunity-Radar/1.0"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


class KfESchoolCollector:
    """KF 글로벌 e-스쿨 공개 표를 대상 국가의 교육 협력 근거로 적재합니다."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        transport: Callable[[str], bytes] | None = None,
    ) -> None:
        self.conn = conn
        self.transport = transport or _default_transport
        self.conn.executescript(KF_ESCHOOL_SCHEMA)
        self.conn.commit()

    def _store_raw_response(self, run_id: int, html: str) -> None:
        # 같은 실행에서 동일 공식 페이지가 한 번만 보존되도록 요청 주소를 해시합니다.
        fingerprint = hashlib.sha256(KF_ESCHOOL_URL.encode("utf-8")).hexdigest()
        self.conn.execute(
            """INSERT OR REPLACE INTO raw_api_response(
                   run_id, source_type, endpoint, request_fingerprint, page_no,
                   fetched_at, http_status, body
               ) VALUES (?, 'KF_ESCHOOL', ?, ?, 1, ?, 200, ?)""",
            (run_id, KF_ESCHOOL_URL, fingerprint, now_utc(), html),
        )

    def _store_course(
        self,
        iso3: str,
        row: list[str],
        fetched_at: str,
    ) -> str | None:
        (
            business_year,
            business_type,
            sending_university,
            study_type,
            course_title,
            semester,
            _receiving_country,
            receiving_university,
            student_count,
        ) = row
        if not course_title or not receiving_university:
            return None

        # 화면에 고정 ID가 없으므로 모든 식별 필드를 묶은 안정 해시를 사용합니다.
        fingerprint_values = [iso3, *row]
        digest = hashlib.sha1(
            "|".join(fingerprint_values).encode("utf-8")
        ).hexdigest()[:20]
        external_id = f"KF-ESCHOOL-{digest}"
        year = _optional_int(business_year)
        published_at = f"{year:04d}-01-01" if year else None
        students = _optional_int(student_count)
        body = (
            f"{business_type} | {study_type} | {sending_university} → "
            f"{receiving_university} | 수강생 {students if students is not None else '미상'}명"
        )
        raw = {
            "business_year": year,
            "business_type": business_type,
            "sending_university": sending_university,
            "study_type": study_type,
            "course_title": course_title,
            "semester": semester,
            "receiving_country": _receiving_country,
            "receiving_university": receiving_university,
            "student_count": students,
        }
        record_id = _source_record(
            self.conn,
            source="KF_ESCHOOL",
            external_id=external_id,
            country=iso3,
            title=course_title,
            body=body,
            published_at=published_at,
            url=KF_ESCHOOL_URL,
            raw=raw,
        )
        self.conn.execute(
            """INSERT INTO kf_eschool_course(
                   external_id, source_record_id, country_iso3, business_year,
                   business_type, sending_university, study_type, course_title,
                   semester, receiving_university, student_count, fetched_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(external_id) DO UPDATE SET
                 source_record_id=excluded.source_record_id,
                 student_count=excluded.student_count,
                 fetched_at=excluded.fetched_at""",
            (
                external_id, record_id, iso3, year, business_type,
                sending_university, study_type, course_title, semester,
                receiving_university, students, fetched_at,
            ),
        )
        self.conn.execute(
            """INSERT INTO evidence(
                   source_record_id, country_iso3, sector_code, event_type,
                   event_date, organizations_json, confidence, supporting_text
               ) VALUES (?, ?, 'korean_studies', 'academic_exchange', ?, ?, 0.95, ?)
               ON CONFLICT(source_record_id, sector_code, event_type) DO UPDATE SET
                 event_date=excluded.event_date,
                 organizations_json=excluded.organizations_json,
                 confidence=excluded.confidence,
                 supporting_text=excluded.supporting_text""",
            (
                record_id,
                iso3,
                published_at,
                json.dumps(
                    [sending_university, receiving_university],
                    ensure_ascii=False,
                ),
                body,
            ),
        )
        return external_id

    def collect(self) -> dict[str, int]:
        # 수집 한 건을 감사 가능한 실행 단위로 남기고 실패 시 원인을 기록합니다.
        upsert_target_countries(self.conn)
        run = IngestionRun(self.conn, "KF_ESCHOOL", {"url": KF_ESCHOOL_URL})
        # 동일한 화면 행이 반복될 수 있으므로 실행 보고서는 고유 ID 기준으로 집계합니다.
        collected_ids = {iso3: set() for iso3 in TARGET_COUNTRIES}
        try:
            raw = self.transport(KF_ESCHOOL_URL)
            html = raw.decode("utf-8-sig", "replace")
            parser = _GlobalESchoolParser()
            parser.feed(html)
            if not parser.rows:
                raise ValueError("KF 글로벌 e-스쿨 결과 표를 찾지 못했습니다.")

            self._store_raw_response(run.id, html)
            fetched_at = date.today().isoformat()
            for row in parser.rows:
                if len(row) != 9:
                    continue
                iso3 = _target_country_iso3(row[6])
                if iso3:
                    external_id = self._store_course(iso3, row, fetched_at)
                    if external_id:
                        collected_ids[iso3].add(external_id)

            counts = {
                iso3: len(external_ids)
                for iso3, external_ids in collected_ids.items()
            }
            for iso3, count in counts.items():
                _coverage(self.conn, iso3, "KF_ESCHOOL", count, fetched_at)
            self.conn.commit()
            run.complete(sum(counts.values()))
            return counts
        except Exception as exc:
            # 다른 수집기와 동일하게 실패 실행 이력과 원인을 감사 로그에 남깁니다.
            run.fail(exc)
            raise
