from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from datetime import date, datetime
from statistics import quantiles

from .taxonomy_v2 import EVENT_WEIGHTS, SECTORS, SOURCE_WEIGHTS

SCORE_VERSION = "v2.1-fixed-benchmarks"

DIMENSION_METRICS = {
    "demand": ("recent_budget", "active_projects", "start_trend", "field_share"),
    "alignment": ("event_strength", "organization_diversity", "recent_event_count"),
    "readiness": ("delivery_projects", "agency_diversity", "continuity"),
    "korea_base": ("academic_depth", "hallyu_clubs", "hallyu_members"),
}

WEIGHT_PRESETS = {
    "enterprise": {"demand": 0.35, "alignment": 0.20, "readiness": 0.35, "korea_base": 0.10},
    "public": {"demand": 0.25, "alignment": 0.35, "readiness": 0.20, "korea_base": 0.20},
    "research": {"demand": 0.15, "alignment": 0.20, "readiness": 0.15, "korea_base": 0.50},
}


def _percentile_bounds(values: list[float]) -> tuple[float, float]:
    values = sorted(values)
    if not values:
        return 0.0, 1.0
    if len(values) < 4:
        return values[0], values[-1] if values[-1] != values[0] else values[0] + 1.0
    cuts = quantiles(values, n=10, method="inclusive")
    return cuts[0], cuts[8]


def _normalize(values: dict[str, float], *, log_scale: bool = False,
               fixed_cap: float | None = None, floor: float = 0.0) -> dict[str, float]:
    if fixed_cap is not None:
        span = max(fixed_cap - floor, 1e-9)
        transformed = {
            key: math.log1p(max(0.0, value - floor)) if log_scale else max(0.0, value - floor)
            for key, value in values.items()
        }
        denominator = math.log1p(span) if log_scale else span
        return {key: 100.0 * min(1.0, value / denominator) for key, value in transformed.items()}
    transformed = {k: math.log1p(max(0.0, v)) if log_scale else v for k, v in values.items()}
    lo, hi = _percentile_bounds(list(transformed.values()))
    if transformed and min(transformed.values()) >= 0:
        lo = 0.0
        hi = max(hi, max(transformed.values()), 1e-9)
    return {k: 100.0 * min(1.0, max(0.0, (v - lo) / (hi - lo))) for k, v in transformed.items()}


def _months_between(then: str, now: date) -> int:
    dt = datetime.fromisoformat(then).date()
    return max(0, (now.year - dt.year) * 12 + now.month - dt.month)


def _raw_features(conn: sqlite3.Connection, sector: str, as_of: date) -> dict[str, dict[str, float]]:
    countries = [r[0] for r in conn.execute("SELECT iso3 FROM country ORDER BY iso3")]
    features = {c: defaultdict(float) for c in countries}
    current_year = as_of.year

    for row in conn.execute(
        """SELECT country_iso3, start_year, end_year, budget, status, agency
           FROM project p WHERE p.sector_code=? OR EXISTS (
             SELECT 1 FROM record_sector rs
             WHERE rs.source_record_id=p.source_record_id AND rs.sector_code=?)""",
        (sector, sector),
    ):
        f = features[row["country_iso3"]]
        budget = float(row["budget"] or 0)
        if row["start_year"] and row["start_year"] >= current_year - 4:
            f["recent_budget"] += budget
        if row["start_year"] and row["start_year"] >= current_year - 2:
            f["recent_starts"] += 1
        if row["start_year"] and current_year - 5 <= row["start_year"] < current_year - 2:
            f["prior_starts"] += 1
        if (row["start_year"] or 0) <= current_year <= (row["end_year"] or current_year):
            f["active_projects"] += 1
        if row["status"] in {"진행", "완료", "active", "completed"}:
            f["delivery_projects"] += 1
        if row["agency"]:
            f.setdefault("agencies", set()).add(row["agency"])
        if row["start_year"]:
            f.setdefault("active_years", set()).update(range(row["start_year"], min(row["end_year"] or current_year, current_year) + 1))

    totals = dict(conn.execute("SELECT country_iso3, COALESCE(SUM(budget), 0) FROM project GROUP BY country_iso3"))
    for country, f in features.items():
        f["field_share"] = f["recent_budget"] / totals.get(country, 1) if totals.get(country, 0) else 0
        f["start_trend"] = (f["recent_starts"] + 1) / (f["prior_starts"] + 1)
        f["agency_diversity"] = len(f.pop("agencies", set()))
        f["continuity"] = min(1.0, len(f.pop("active_years", set())) / 5)

    for row in conn.execute(
        """SELECT e.country_iso3, e.event_type, e.event_date, e.organizations_json, e.confidence,
                  r.source_type
           FROM evidence e JOIN source_record r ON r.id=e.source_record_id
           WHERE e.sector_code=? OR EXISTS (
             SELECT 1 FROM record_sector rs
             WHERE rs.source_record_id=e.source_record_id AND rs.sector_code=?)""",
        (sector, sector),
    ):
        f = features[row["country_iso3"]]
        months = _months_between(row["event_date"], as_of) if row["event_date"] else 60
        time_weight = math.exp(-math.log(2) * months / 18)
        value = time_weight * EVENT_WEIGHTS.get(row["event_type"], 0.1) * SOURCE_WEIGHTS.get(row["source_type"], 0.8) * row["confidence"]
        f["event_strength"] += value
        f.setdefault("organizations", set()).update(json.loads(row["organizations_json"]))
        if months <= 24:
            f["recent_event_count"] += 1
    for f in features.values():
        f["organization_diversity"] = len(f.pop("organizations", set()))

    for row in conn.execute("SELECT * FROM academic_program"):
        f = features[row["country_iso3"]]
        f["academic_depth"] += (2 * row["bachelor"] + 3 * row["master"] + 4 * row["doctorate"]
                                + row["language_course"] + 2 * row["research_center"]
                                + row["sejong_institute"] + 0.5 * row["korea_corner"])
    latest_hallyu = conn.execute(
        """SELECT h.* FROM hallyu_stat h JOIN
             (SELECT country_iso3, MAX(year) y FROM hallyu_stat GROUP BY country_iso3) x
             ON h.country_iso3=x.country_iso3 AND h.year=x.y"""
    ).fetchall()
    for row in latest_hallyu:
        f = features[row["country_iso3"]]
        f["hallyu_clubs"] = row["club_count"] or 0
        f["hallyu_members"] = row["member_count"] or 0
    return features


def _confidence(conn: sqlite3.Connection, country: str, weights: dict[str, float], as_of: date) -> float:
    required = {"KOICA": weights["demand"] + weights["readiness"], "LOD": weights["alignment"] / 2,
                "MOFA": weights["alignment"] / 2, "KF": weights["korea_base"]}
    required = {k: v for k, v in required.items() if v > 0}
    rows = {r["source_type"]: r for r in conn.execute("SELECT * FROM source_coverage WHERE country_iso3=?", (country,))}
    total_weight = sum(required.values()) or 1
    completeness = sum(w for source, w in required.items() if source in rows) / total_weight
    diversity = len(set(required) & set(rows)) / len(required)
    freshness_parts = []
    for source in required:
        if source not in rows:
            freshness_parts.append(0.0)
        else:
            age = _months_between(rows[source]["observed_at"], as_of)
            freshness_parts.append(math.exp(-math.log(2) * age / 24))
    freshness = sum(freshness_parts) / len(freshness_parts)
    return 100 * (0.40 * completeness + 0.30 * freshness + 0.30 * diversity)


def calculate_scores(conn: sqlite3.Connection, as_of: date) -> int:
    conn.execute("DELETE FROM score_component WHERE score_id IN (SELECT id FROM score_snapshot WHERE score_version=? AND as_of_date=?)", (SCORE_VERSION, as_of.isoformat()))
    conn.execute("DELETE FROM score_snapshot WHERE score_version=? AND as_of_date=?", (SCORE_VERSION, as_of.isoformat()))
    written = 0
    for sector, cfg in SECTORS.items():
        features = _raw_features(conn, sector, as_of)
        metrics = {
            "recent_budget": _normalize({c: f["recent_budget"] for c, f in features.items()}, log_scale=True, fixed_cap=50_000_000),
            "active_projects": _normalize({c: f["active_projects"] for c, f in features.items()}, log_scale=True, fixed_cap=10),
            "start_trend": _normalize({c: f["start_trend"] for c, f in features.items()}, fixed_cap=3, floor=1),
            "field_share": _normalize({c: f["field_share"] for c, f in features.items()}, fixed_cap=0.60),
            "event_strength": _normalize({c: f["event_strength"] for c, f in features.items()}, log_scale=True, fixed_cap=4),
            "organization_diversity": _normalize({c: f["organization_diversity"] for c, f in features.items()}, log_scale=True, fixed_cap=12),
            "recent_event_count": _normalize({c: f["recent_event_count"] for c, f in features.items()}, log_scale=True, fixed_cap=10),
            "delivery_projects": _normalize({c: f["delivery_projects"] for c, f in features.items()}, log_scale=True, fixed_cap=10),
            "agency_diversity": _normalize({c: f["agency_diversity"] for c, f in features.items()}, log_scale=True, fixed_cap=8),
            "continuity": _normalize({c: f["continuity"] for c, f in features.items()}, fixed_cap=1),
            "academic_depth": _normalize({c: f["academic_depth"] for c, f in features.items()}, log_scale=True, fixed_cap=60),
            "hallyu_clubs": _normalize({c: f["hallyu_clubs"] for c, f in features.items()}, log_scale=True, fixed_cap=100),
            "hallyu_members": _normalize({c: f["hallyu_members"] for c, f in features.items()}, log_scale=True, fixed_cap=1_000_000),
        }
        for country, f in features.items():
            demand = 0.35 * metrics["recent_budget"][country] + 0.25 * metrics["active_projects"][country] + 0.20 * metrics["start_trend"][country] + 0.20 * metrics["field_share"][country]
            alignment = 0.50 * metrics["event_strength"][country] + 0.30 * metrics["organization_diversity"][country] + 0.20 * metrics["recent_event_count"][country]
            readiness = 0.40 * metrics["delivery_projects"][country] + 0.30 * metrics["agency_diversity"][country] + 0.30 * metrics["continuity"][country]
            korea_base = 0.55 * metrics["academic_depth"][country] + 0.20 * metrics["hallyu_clubs"][country] + 0.25 * metrics["hallyu_members"][country]
            dimensions = {"demand": demand, "alignment": alignment, "readiness": readiness, "korea_base": korea_base}
            weights = cfg["weights"]
            score = sum(weights[k] * dimensions[k] for k in weights)
            scenarios = []
            for key in weights:
                for factor in (0.8, 1.2):
                    varied = dict(weights); varied[key] *= factor
                    z = sum(varied.values()); varied = {k: v / z for k, v in varied.items()}
                    scenarios.append(sum(varied[k] * dimensions[k] for k in varied))
            risk = conn.execute("SELECT MAX(warning_level) FROM safety_notice WHERE country_iso3=?", (country,)).fetchone()[0]
            confidence = _confidence(conn, country, weights, as_of)
            cur = conn.execute(
                """INSERT INTO score_snapshot(country_iso3, sector_code, score_version, as_of_date,
                           demand_score, alignment_score, readiness_score, korea_base_score,
                           opportunity_score, data_confidence, risk_level, sensitivity_low, sensitivity_high)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (country, sector, SCORE_VERSION, as_of.isoformat(), demand, alignment, readiness,
                 korea_base, score, confidence, risk, min(scenarios), max(scenarios)),
            )
            score_id = cur.lastrowid
            for code, value in dimensions.items():
                conn.execute(
                    "INSERT INTO score_component(score_id, component_code, normalized_value, contribution, detail_json) VALUES (?, ?, ?, ?, ?)",
                    (
                        score_id, code, value, weights[code] * value,
                        json.dumps(
                            {
                                "weight": weights[code],
                                "metrics": {
                                    metric: {"raw": f[metric], "normalized": metrics[metric][country]}
                                    for metric in DIMENSION_METRICS[code]
                                },
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
            written += 1
    conn.commit()
    return written


def normalize_dimension_weights(weights: dict[str, float]) -> dict[str, float]:
    if set(weights) != set(DIMENSION_METRICS):
        raise ValueError(f"weights must contain exactly: {', '.join(DIMENSION_METRICS)}")
    if any(value < 0 for value in weights.values()):
        raise ValueError("weights cannot be negative")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("at least one weight must be positive")
    return {key: value / total for key, value in weights.items()}


def recommend_with_options(
    conn: sqlite3.Connection,
    sector: str,
    limit: int = 5,
    *,
    region: str | None = None,
    country_iso3: str | None = None,
    max_risk: int | None = None,
    min_confidence: float = 0,
    weights: dict[str, float] | None = None,
) -> list[dict]:
    if sector not in SECTORS:
        raise ValueError(f"Unsupported sector: {sector}")
    applied_weights = normalize_dimension_weights(weights or SECTORS[sector]["weights"])
    clauses = [
        "s.sector_code=?",
        "s.score_version=?",
        "s.as_of_date=(SELECT MAX(as_of_date) FROM score_snapshot WHERE sector_code=? AND score_version=?)",
        "s.data_confidence>=?",
    ]
    params: list[object] = [sector, SCORE_VERSION, sector, SCORE_VERSION, min_confidence]
    if region:
        clauses.append("c.region_code=?")
        params.append(region)
    if country_iso3:
        clauses.append("s.country_iso3=?")
        params.append(country_iso3.upper())
    if max_risk is not None:
        clauses.append("COALESCE(s.risk_level, 0)<=?")
        params.append(max_risk)
    rows = conn.execute(
        f"""SELECT s.*, c.name_ko, c.region_code FROM score_snapshot s
            JOIN country c ON c.iso3=s.country_iso3
            WHERE {' AND '.join(clauses)}""",
        params,
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        values = {
            "demand": item["demand_score"], "alignment": item["alignment_score"],
            "readiness": item["readiness_score"], "korea_base": item["korea_base_score"],
        }
        item["ranking_score"] = sum(applied_weights[key] * values[key] for key in values)
        item["applied_weights"] = applied_weights
        item["top_components"] = [
            {"code": key, "score": values[key], "contribution": applied_weights[key] * values[key]}
            for key in sorted(values, key=lambda key: applied_weights[key] * values[key], reverse=True)[:3]
        ]
        result.append(item)
    result.sort(key=lambda item: (item["data_confidence"] < 60, -item["ranking_score"], item["country_iso3"]))
    return result[:limit]


def recommendations(conn: sqlite3.Connection, sector: str, limit: int = 5) -> list[dict]:
    return recommend_with_options(conn, sector, limit)
