from __future__ import annotations

# 0. 모듈 불러오기
import argparse
import json
import sqlite3
from pathlib import Path


# 1. 기본 실제 데이터베이스 경로 정의
ALGORITHM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ALGORITHM_ROOT / "data" / "radar_real.db"


# 2. 수집 건수·기간·중복 여부를 한 번에 확인
def build_summary(database: Path) -> dict:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row

    def rows(sql: str) -> list[dict]:
        return [dict(row) for row in connection.execute(sql)]

    try:
        return {
            "database": str(database.resolve()),
            "source_records": rows(
                """SELECT source_type, COUNT(*) AS record_count
                   FROM source_record
                   GROUP BY source_type
                   ORDER BY source_type"""
            ),
            "kf_eschool_by_country": rows(
                """SELECT country_iso3, COUNT(*) AS course_count,
                          MIN(business_year) AS first_year,
                          MAX(business_year) AS last_year,
                          SUM(COALESCE(student_count, 0)) AS total_students
                   FROM kf_eschool_course
                   GROUP BY country_iso3
                   ORDER BY country_iso3"""
            ),
            "duplicate_kf_eschool_ids": connection.execute(
                """SELECT COUNT(*)
                   FROM (
                       SELECT external_id
                       FROM kf_eschool_course
                       GROUP BY external_id
                       HAVING COUNT(*) > 1
                   )"""
            ).fetchone()[0],
            "latest_ingestion_runs": rows(
                """SELECT id, source_type, status, record_count, finished_at
                   FROM ingestion_run
                   ORDER BY id DESC
                   LIMIT 10"""
            ),
        }
    finally:
        connection.close()


# 3. 명령행에서 DB 경로를 받아 JSON 상태 출력
def main() -> None:
    parser = argparse.ArgumentParser(description="수집된 실제 데이터 상태를 점검합니다.")
    parser.add_argument("--db", default=str(DEFAULT_DATABASE))
    args = parser.parse_args()
    print(
        json.dumps(
            build_summary(Path(args.db)),
            ensure_ascii=False,
            indent=2,
        )
    )


# 4. 파일을 직접 실행할 때 점검 시작
if __name__ == "__main__":
    main()
