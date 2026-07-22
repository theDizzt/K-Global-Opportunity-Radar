from __future__ import annotations

import hashlib
import sqlite3
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from .ingest import _coverage, _source_record
from .standards import record_quality_issue, resolve_country_iso3


KF_STUDIES_URL = "https://www.kf.or.kr/koreanstudies/koreaStudiesList.do"
KF_DATA_PERIOD_END = "2017-12-31"


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def load_kf_academic_html(conn: sqlite3.Connection, path: str | Path) -> dict[str, int]:
    """Load the official KF HTML-table Excel export for supported countries.

    The KF endpoint returns an HTML table with an Excel content type.  The
    published description says the series is based on the 2016--2017 survey,
    so that period end is stored separately from the collection date.
    """
    raw = Path(path).read_bytes()
    if b"<table" not in raw.lower():
        raise ValueError("KF studies export is not an HTML table")
    parser = _TableParser()
    parser.feed(raw.decode("utf-8-sig"))
    if not parser.rows or parser.rows[0][:5] != ["지역", "국가", "대학형태", "대학명", "한국학 제공 형태"]:
        raise ValueError("Unexpected KF studies export columns")

    counts: dict[str, int] = {"VNM": 0, "IDN": 0, "MNG": 0}
    collected_at = date.today().isoformat()
    for row in parser.rows[1:]:
        if len(row) < 5:
            continue
        region, country_name, university_type, university, offering = row[:5]
        iso3 = resolve_country_iso3(conn, country_name)
        if iso3 not in counts:
            continue
        if not university:
            record_quality_issue(
                conn, source_type="KF", issue_type="missing_required_value",
                field_name="university_name", raw_value=row,
            )
            continue
        digest = hashlib.sha1(f"{iso3}|{university}".encode("utf-8")).hexdigest()[:16]
        external_id = f"KF-STUDIES-{digest}"
        record_id = _source_record(
            conn,
            source="KF",
            external_id=external_id,
            country=iso3,
            title=university,
            body=f"한국학 제공 형태: {offering or '미기재'}",
            published_at=KF_DATA_PERIOD_END,
            url=KF_STUDIES_URL,
            raw={
                "region": region,
                "country": country_name,
                "university_type": university_type,
                "university_name": university,
                "offering_type": offering,
                "data_period": "2016-2017 survey; subsequent updates may lag",
                "collected_at": collected_at,
            },
        )
        flags = {
            "bachelor": int("학사" in offering),
            "master": int("석사" in offering),
            "doctorate": int("박사" in offering),
            "language_course": int("교양" in offering),
            "research_center": int("센터" in offering),
            "sejong_institute": 0,
            "korea_corner": 0,
        }
        conn.execute(
            """INSERT INTO academic_program(
                       external_id, source_record_id, country_iso3, university_name,
                       bachelor, master, doctorate, language_course, research_center,
                       sejong_institute, korea_corner, reference_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(external_id) DO UPDATE SET
                     source_record_id=excluded.source_record_id,
                     university_name=excluded.university_name,
                     bachelor=excluded.bachelor, master=excluded.master,
                     doctorate=excluded.doctorate, language_course=excluded.language_course,
                     research_center=excluded.research_center,
                     reference_date=excluded.reference_date""",
            (external_id, record_id, iso3, university, *(flags[key] for key in flags), KF_DATA_PERIOD_END),
        )
        counts[iso3] += 1

    for iso3, count in counts.items():
        _coverage(conn, iso3, "KF_STUDIES", count, collected_at)
    conn.commit()
    return counts
