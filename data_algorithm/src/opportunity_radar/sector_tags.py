from __future__ import annotations

import sqlite3

from .multisector import classify_sectors
from .taxonomy_v2 import SECTORS


def upsert_record_sectors(
    conn: sqlite3.Connection,
    source_record_id: int,
    text: str,
    *,
    primary_sector: str | None = None,
) -> int:
    ranked = classify_sectors(text)
    if primary_sector not in SECTORS:
        primary_sector = ranked[0][0] if ranked else None
    by_code = {code: (confidence, hits) for code, confidence, hits in ranked}
    if primary_sector and primary_sector not in by_code:
        by_code[primary_sector] = (1.0, 0)
    conn.execute("DELETE FROM record_sector WHERE source_record_id=?", (source_record_id,))
    for code, (confidence, hits) in by_code.items():
        conn.execute(
            """INSERT INTO record_sector(source_record_id, sector_code, confidence,
                       is_primary, mapping_method)
               VALUES (?, ?, ?, ?, ?)""",
            (
                source_record_id, code, confidence, int(code == primary_sector),
                "explicit+keyword-v2" if hits == 0 else "keyword-v2",
            ),
        )
    return len(by_code)


def backfill_record_sectors(conn: sqlite3.Connection) -> int:
    count = 0
    rows = conn.execute(
        """SELECT r.id, r.title, r.body, p.sector_code AS project_sector
           FROM source_record r LEFT JOIN project p ON p.source_record_id=r.id"""
    ).fetchall()
    for row in rows:
        count += upsert_record_sectors(
            conn, row["id"], f'{row["title"]}\n{row["body"]}',
            primary_sector=row["project_sector"],
        )
    return count
