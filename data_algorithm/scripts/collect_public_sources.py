from __future__ import annotations

# 0. 모듈 불러오기
import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from opportunity_radar.config import load_env
from opportunity_radar.db import connect, initialize
from opportunity_radar.kf_pipeline import KfCollector
from opportunity_radar.kf_eschool import KfESchoolCollector
from opportunity_radar.kf_studies import load_kf_academic_html
from opportunity_radar.koica_pipeline import PROJECT_TYPES
from opportunity_radar.mofa_lod import MofaLodCollector
from opportunity_radar.mofa_pipeline import MofaCollector
from opportunity_radar.resilient_koica import ResilientKoicaCollector


# 1. 프로젝트 기준 경로와 지원 데이터 출처 정의
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALGORITHM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ALGORITHM_ROOT / "data" / "radar_real.db"
DEFAULT_REPORT = ALGORITHM_ROOT / "outputs" / "collection_report.json"
SUPPORTED_SOURCES = (
    "lod",
    "kf_eschool",
    "kf",
    "mofa",
    "koica",
    "kf_academic",
)


# 2. 실제 데이터 수집 명령행 옵션 구성
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect real MOFA LOD, KF, MOFA REST, and KOICA data."
    )
    parser.add_argument("--db", default=str(DEFAULT_DATABASE))
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=SUPPORTED_SOURCES,
        default=SUPPORTED_SOURCES,
        help="수집할 출처 목록. 인증키나 원본 파일이 없으면 해당 출처만 건너뜁니다.",
    )
    parser.add_argument("--page-size", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--from-year", type=int, default=1991)
    parser.add_argument("--to-year", type=int, default=date.today().year)
    parser.add_argument("--project-type", action="append")
    parser.add_argument("--min-request-interval", type=float, default=3.0)
    parser.add_argument(
        "--kf-academic-input",
        default=str(ALGORITHM_ROOT / "data" / "raw" / "kf_korean_studies.xlsx"),
    )
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument(
        "--strict",
        action="store_true",
        help="요청한 출처가 누락되거나 실패하면 비정상 종료합니다.",
    )
    return parser


# 3. 루트 .env에서 공공데이터포털 인증키 확인
def _service_key() -> str:
    return (
        os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip()
        or os.getenv("KOICA_SERVICE_KEY", "").strip()
    )


# 4. 출처 하나의 수집 결과를 공통 형식으로 기록
def _collect_source(
    results: dict[str, dict],
    source_name: str,
    collector: Callable[[], dict[str, int]],
) -> None:
    try:
        counts = collector()
        results[source_name] = {
            "status": "complete",
            "countries": counts,
            "total": sum(counts.values()),
        }
    except Exception as exc:
        results[source_name] = {
            "status": "failed",
            "reason": f"{type(exc).__name__}: {exc}",
        }


# 5. 수집 결과를 재현 가능한 JSON 실행 보고서로 저장
def _write_report(database: Path, report_path: Path, results: dict[str, dict]) -> dict:
    payload = {
        "database": str(database.resolve()),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "sources": results,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


# 6. 선택한 실제 데이터 출처를 순서대로 수집
def main() -> None:
    args = build_parser().parse_args()
    load_env(PROJECT_ROOT / ".env")

    database = Path(args.db)
    report_path = Path(args.report)
    requested = tuple(dict.fromkeys(args.sources))
    key = _service_key()
    results: dict[str, dict] = {}

    database.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(database)
    initialize(connection)
    try:
        # 6.1. 외교부 LOD는 별도 인증키 없이 공식 SPARQL 원문을 수집합니다.
        if "lod" in requested:
            _collect_source(
                results,
                "LOD",
                lambda: MofaLodCollector(connection).collect(
                    page_size=min(args.page_size, 200),
                    max_pages=args.max_pages,
                ),
            )

        # 6.2. KF 글로벌 e-스쿨 공개 표는 인증키 없이 실제 강좌 자료를 수집합니다.
        if "kf_eschool" in requested:
            _collect_source(
                results,
                "KF_ESCHOOL",
                lambda: KfESchoolCollector(connection).collect(),
            )

        # 6.3. KF·MOFA REST API는 공공데이터포털 인증키가 있을 때 실행합니다.
        if "kf" in requested:
            if key:
                _collect_source(
                    results,
                    "KF",
                    lambda: KfCollector(connection, key).collect(
                        page_size=args.page_size,
                        max_pages=args.max_pages,
                    ),
                )
            else:
                results["KF"] = {
                    "status": "skipped",
                    "reason": "DATA_GO_KR_SERVICE_KEY 또는 KOICA_SERVICE_KEY가 필요합니다.",
                }

        if "mofa" in requested:
            if key:
                _collect_source(
                    results,
                    "MOFA",
                    lambda: MofaCollector(connection, key).collect(
                        page_size=args.page_size,
                        max_pages=args.max_pages,
                    ),
                )
            else:
                results["MOFA"] = {
                    "status": "skipped",
                    "reason": "DATA_GO_KR_SERVICE_KEY 또는 KOICA_SERVICE_KEY가 필요합니다.",
                }

        # 6.4. KOICA는 연도·사업유형 단위 실패를 격리하는 복원형 수집기를 사용합니다.
        if "koica" in requested:
            if key:
                _collect_source(
                    results,
                    "KOICA",
                    lambda: ResilientKoicaCollector(
                        connection,
                        key,
                        min_request_interval=args.min_request_interval,
                    ).collect(
                        years=range(args.from_year, args.to_year + 1),
                        page_size=args.page_size,
                        project_types=(
                            tuple(args.project_type)
                            if args.project_type
                            else PROJECT_TYPES
                        ),
                    ),
                )
            else:
                results["KOICA"] = {
                    "status": "skipped",
                    "reason": "DATA_GO_KR_SERVICE_KEY 또는 KOICA_SERVICE_KEY가 필요합니다.",
                }

        # 6.5. KF 한국학 파일은 공식 원본 파일이 준비된 경우에만 적재합니다.
        if "kf_academic" in requested:
            academic_path = Path(args.kf_academic_input)
            if academic_path.exists():
                _collect_source(
                    results,
                    "KF_ACADEMIC",
                    lambda: load_kf_academic_html(connection, academic_path),
                )
            else:
                results["KF_ACADEMIC"] = {
                    "status": "skipped",
                    "reason": f"공식 원본 파일이 없습니다: {academic_path}",
                }
    finally:
        connection.close()

    payload = _write_report(database, report_path, results)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    # 6.6. strict 모드는 누락·실패 출처가 하나라도 있으면 CI에서 실패로 처리합니다.
    if args.strict and any(
        item["status"] != "complete" for item in results.values()
    ):
        raise SystemExit(1)


# 7. 파일을 직접 실행할 때 실제 데이터 수집 시작
if __name__ == "__main__":
    main()
