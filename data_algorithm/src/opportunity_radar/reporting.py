from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
from datetime import date
from pathlib import Path

from .explain import build_explanation_context, template_explanation
from .scoring import SCORE_VERSION, calculate_scores, recommendations
from .taxonomy_v2 import SECTORS


CLEAN_VIEWS = (
    "country_master", "oda_project_fact", "diplomatic_activity_fact",
    "korea_base_fact", "risk_fact", "cooperation_signal_yearly", "evidence_document",
)


def _scalar(conn: sqlite3.Connection, sql: str, params=()):
    return conn.execute(sql, params).fetchone()[0]


def _rows_hash(conn: sqlite3.Connection, as_of: str) -> str:
    rows = conn.execute(
        """SELECT country_iso3, sector_code, demand_score, alignment_score,
                  readiness_score, korea_base_score, opportunity_score,
                  data_confidence, risk_level, sensitivity_low, sensitivity_high
           FROM score_snapshot WHERE score_version=? AND as_of_date=?
           ORDER BY country_iso3, sector_code""",
        (SCORE_VERSION, as_of),
    ).fetchall()
    payload = json.dumps([list(row) for row in rows], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_run_report(conn: sqlite3.Connection, as_of: str) -> dict:
    source_counts = {
        row[0]: row[1] for row in conn.execute(
            "SELECT source_type, COUNT(*) FROM source_record GROUP BY source_type ORDER BY source_type"
        )
    }
    coverage = [dict(row) for row in conn.execute(
        "SELECT country_iso3, source_type, observed_at, record_count FROM source_coverage ORDER BY country_iso3, source_type"
    )]
    runs = [dict(row) for row in conn.execute(
        """SELECT id, source_type, started_at, finished_at, status, record_count, error_message
           FROM ingestion_run ORDER BY id"""
    )]
    return {
        "generated_at": date.today().isoformat(),
        "as_of_date": as_of,
        "score_version": SCORE_VERSION,
        "target_countries": ["VNM", "IDN", "MNG"],
        "enabled_sectors": list(SECTORS),
        "counts": {
            "source_records": source_counts,
            "projects": _scalar(conn, "SELECT COUNT(*) FROM project"),
            "academic_programs": _scalar(conn, "SELECT COUNT(*) FROM academic_program"),
            "evidence": _scalar(conn, "SELECT COUNT(*) FROM evidence"),
            "safety_notices": _scalar(conn, "SELECT COUNT(*) FROM safety_notice"),
            "score_snapshots": _scalar(
                conn, "SELECT COUNT(*) FROM score_snapshot WHERE score_version=? AND as_of_date=?",
                (SCORE_VERSION, as_of),
            ),
            "lineage_records": _scalar(conn, "SELECT COUNT(*) FROM record_lineage"),
            "open_quality_issues": _scalar(conn, "SELECT COUNT(*) FROM data_quality_issue WHERE status='open'"),
        },
        "coverage": coverage,
        "ingestion_runs": runs,
        "known_limitations": [
            "KOICA 공식 API 두 계열이 수집 시점에 504/timeout을 반환하여 실제 KOICA 사업 행은 아직 0건입니다."
            if _scalar(conn, "SELECT COUNT(*) FROM project") == 0 else None,
            "KF 한국학 통계는 공식 안내상 2016~2017 전수조사 기반이며 후속 갱신 시차가 있을 수 있습니다.",
            "MOFA 인사이트는 별도 공개 API·재이용 조건이 확인되지 않아 참조 전용으로 제외했습니다.",
        ],
    }


def validate(conn: sqlite3.Connection, as_of: str) -> dict:
    before = _rows_hash(conn, as_of)
    calculate_scores(conn, date.fromisoformat(as_of))
    calculate_scores(conn, date.fromisoformat(as_of))
    after = _rows_hash(conn, as_of)
    score_rows = conn.execute(
        "SELECT * FROM score_snapshot WHERE score_version=? AND as_of_date=?",
        (SCORE_VERSION, as_of),
    ).fetchall()
    widths = [row["sensitivity_high"] - row["sensitivity_low"] for row in score_rows]
    dominance = []
    for row in conn.execute(
        """SELECT sc.score_id, MAX(sc.contribution) max_contribution,
                  SUM(sc.contribution) total_contribution
           FROM score_component sc JOIN score_snapshot s ON s.id=sc.score_id
           WHERE s.score_version=? AND s.as_of_date=? GROUP BY sc.score_id""",
        (SCORE_VERSION, as_of),
    ):
        dominance.append(row["max_contribution"] / row["total_contribution"] if row["total_contribution"] else 0)
    duplicates = _scalar(
        conn,
        """SELECT COUNT(*) FROM (
             SELECT source_type, external_id FROM source_record
             GROUP BY source_type, external_id HAVING COUNT(*)>1)""",
    )
    url_total = _scalar(conn, "SELECT COUNT(*) FROM source_record")
    url_present = _scalar(conn, "SELECT COUNT(*) FROM source_record WHERE source_url IS NOT NULL AND source_url<>''")
    return {
        "score_count": len(score_rows),
        "expected_score_count": 24,
        "score_range_valid": all(0 <= row["opportunity_score"] <= 100 for row in score_rows),
        "reproducible": before == after,
        "snapshot_sha256": after,
        "duplicate_source_keys": duplicates,
        "max_dimension_share": round(max(dominance, default=0), 4),
        "max_weight_sensitivity_width": round(max(widths, default=0), 4),
        "average_weight_sensitivity_width": round(sum(widths) / len(widths), 4) if widths else 0,
        "source_url_coverage": round(url_present / url_total, 4) if url_total else 0,
        "koica_project_count": _scalar(conn, "SELECT COUNT(*) FROM project"),
        "open_quality_issues": _scalar(conn, "SELECT COUNT(*) FROM data_quality_issue WHERE status='open'"),
    }


def export_view(conn: sqlite3.Connection, view: str, destination: Path) -> int:
    cursor = conn.execute(f'SELECT * FROM "{view}"')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([column[0] for column in cursor.description])
        rows = cursor.fetchall()
        writer.writerows([list(row) for row in rows])
    return len(rows)


def generate_outputs(conn: sqlite3.Connection, output_dir: str | Path, as_of: str) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_report = build_run_report(conn, as_of)
    validation = validate(conn, as_of)
    run_report["validation"] = validation
    (output_dir / "run_report.json").write_text(
        json.dumps(run_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    samples = {}
    for sector in SECTORS:
        rows = recommendations(conn, sector, 3)
        for row in rows:
            row["explanation"] = template_explanation(build_explanation_context(conn, row["id"]))
        samples[sector] = rows
    (output_dir / "recommendation_samples.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    clean_counts = {
        view: export_view(conn, view, output_dir / "clean" / f"{view}.csv") for view in CLEAN_VIEWS
    }
    with (output_dir / "raw_manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["kind", "source", "identifier", "fetched_at", "status", "bytes_or_records"])
        for row in conn.execute(
            """SELECT source_type, endpoint, request_fingerprint, fetched_at, http_status,
                      length(CAST(body AS BLOB)) FROM raw_api_response ORDER BY id"""
        ):
            writer.writerow(["api_response", *row])
        kf_file = Path("data/raw/kf_korean_studies.xlsx")
        if kf_file.exists():
            writer.writerow(["official_download", "KF_STUDIES", str(kf_file),
                             date.fromtimestamp(kf_file.stat().st_mtime).isoformat(), "200", kf_file.stat().st_size])

    status = "PASS" if (
        validation["score_count"] == 24 and validation["score_range_valid"]
        and validation["reproducible"] and validation["duplicate_source_keys"] == 0
        and validation["max_dimension_share"] <= 0.70
        and validation["koica_project_count"] > 0
    ) else "REVIEW"
    lines = [
        "# 알고리즘 검증 결과", "", f"- 종합 상태: **{status}**",
        f"- 점수 스냅샷: {validation['score_count']}/24",
        f"- 재현성: {'통과' if validation['reproducible'] else '실패'}",
        f"- 점수 범위 0~100: {'통과' if validation['score_range_valid'] else '실패'}",
        f"- 중복 출처키: {validation['duplicate_source_keys']}건",
        f"- 최대 단일 차원 기여비중: {validation['max_dimension_share']:.1%}",
        f"- ±20% 가중치 민감도 최대 폭: {validation['max_weight_sensitivity_width']:.2f}점",
        f"- 원문 URL 충족률: {validation['source_url_coverage']:.1%}",
        "", "## 반드시 보완할 외부 데이터", "",
        f"- KOICA 사업 적재: {validation['koica_project_count']}건. API 장애가 해소되면 재수집 후 동일 검증을 다시 실행해야 합니다.",
        "- KF 한국학 기반은 2016~2017 조사 기준이므로 최신성 한계를 리포트에 표시해야 합니다.",
        "", "## 정제 데이터셋 건수", "",
    ] + [f"- `{name}`: {count}건" for name, count in clean_counts.items()]
    (output_dir / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": status, "clean_counts": clean_counts, "validation": validation}
