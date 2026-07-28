from __future__ import annotations

# 0. 모듈 불러오기
import argparse
import json
import os
from datetime import date
from pathlib import Path

from opportunity_radar.config import load_env, require_setting
from opportunity_radar.db import connect, initialize
from opportunity_radar.koica_pipeline import PROJECT_TYPES
from opportunity_radar.resilient_koica import ResilientKoicaCollector


# 1. 루트 환경설정과 실제 데이터베이스 기본 경로 정의
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALGORITHM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ALGORITHM_ROOT / "data" / "radar_real.db"


# 2. KOICA 전용 수집 옵션 구성
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect KOICA projects for Vietnam, Indonesia, and Mongolia."
    )
    parser.add_argument("--db", default=None)
    parser.add_argument("--from-year", type=int, default=1991)
    parser.add_argument("--to-year", type=int, default=date.today().year)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument(
        "--project-type",
        action="append",
        help="특정 KOICA 사업유형만 수집할 때 여러 번 지정할 수 있습니다.",
    )
    parser.add_argument("--min-request-interval", type=float, default=3.0)
    parser.add_argument("--max-retries", type=int, default=3)
    return parser


# 3. 공공데이터포털 인증키로 KOICA 전체기간 데이터 수집
def main() -> None:
    args = build_parser().parse_args()
    load_env(PROJECT_ROOT / ".env")

    database = Path(
        args.db
        or os.getenv("RADAR_DB_PATH", "").strip()
        or DEFAULT_DATABASE
    )
    database.parent.mkdir(parents=True, exist_ok=True)

    connection = connect(database)
    initialize(connection)
    try:
        collector = ResilientKoicaCollector(
            connection,
            require_setting("KOICA_SERVICE_KEY"),
            min_request_interval=args.min_request_interval,
            max_retries=args.max_retries,
        )
        counts = collector.collect(
            years=range(args.from_year, args.to_year + 1),
            page_size=args.page_size,
            project_types=(
                tuple(args.project_type)
                if args.project_type
                else PROJECT_TYPES
            ),
        )
    finally:
        connection.close()

    print(
        json.dumps(
            {
                "database": str(database.resolve()),
                "countries": counts,
                "total": sum(counts.values()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


# 4. 파일을 직접 실행할 때 KOICA 수집 시작
if __name__ == "__main__":
    main()
