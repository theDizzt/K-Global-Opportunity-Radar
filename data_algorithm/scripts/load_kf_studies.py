from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.kf_studies import load_kf_academic_html


# 1. 프로젝트 기준 실제 데이터 경로 정의
ALGORITHM_ROOT = Path(__file__).resolve().parents[1]


# 2. 공식 KF 한국학 원본 파일을 정규화 테이블에 적재
def main() -> None:
    parser = argparse.ArgumentParser(description="Load the official KF Korean-studies export")
    parser.add_argument("--db", default=str(ALGORITHM_ROOT / "data" / "radar_real.db"))
    parser.add_argument(
        "--input",
        default=str(ALGORITHM_ROOT / "data" / "raw" / "kf_korean_studies.xlsx"),
    )
    args = parser.parse_args()
    connection = connect(args.db)
    initialize(connection)
    try:
        counts = load_kf_academic_html(connection, args.input)
        initialize(connection)
    finally:
        connection.close()
    print(json.dumps(counts, ensure_ascii=False, indent=2))


# 3. 파일을 직접 실행할 때 KF 한국학 자료 적재 시작
if __name__ == "__main__":
    main()
