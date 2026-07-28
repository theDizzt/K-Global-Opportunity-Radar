from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Iterable

from .project_history import ensure_project_history_schema, sync_internal_projects
from .taxonomy_v2 import SECTORS


SIGNAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS signal_event (
    signal_id TEXT PRIMARY KEY,
    evidence_id INTEGER NOT NULL REFERENCES evidence(id),
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    sector_code TEXT NOT NULL REFERENCES sector(code),
    event_type TEXT NOT NULL,
    event_tier TEXT NOT NULL,
    event_year INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    base_weight REAL NOT NULL,
    organizations_json TEXT NOT NULL DEFAULT '[]',
    source_url TEXT,
    eligible_predictor INTEGER NOT NULL DEFAULT 1,
    UNIQUE(evidence_id)
);

CREATE TABLE IF NOT EXISTS cooperation_signal_panel (
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    sector_code TEXT NOT NULL REFERENCES sector(code),
    snapshot_year INTEGER NOT NULL,
    horizon_years INTEGER NOT NULL,
    signal_count_1y REAL NOT NULL,
    signal_count_3y REAL NOT NULL,
    signal_weight_3y REAL NOT NULL,
    signal_trend REAL NOT NULL,
    tier_ab_count_3y REAL NOT NULL,
    source_diversity_3y REAL NOT NULL,
    partner_diversity_3y REAL NOT NULL,
    prior_project_count_3y REAL NOT NULL,
    prior_project_count_5y REAL NOT NULL,
    years_since_last_project REAL NOT NULL,
    data_coverage REAL NOT NULL,
    outcome_new_project INTEGER NOT NULL,
    outcome_project_count INTEGER NOT NULL,
    outcome_commitment REAL NOT NULL,
    PRIMARY KEY(country_iso3, sector_code, snapshot_year, horizon_years)
);

CREATE TABLE IF NOT EXISTS signal_validation_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    horizon_years INTEGER NOT NULL,
    train_end_year INTEGER NOT NULL,
    test_start_year INTEGER NOT NULL,
    status TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    positive_count INTEGER NOT NULL,
    feature_names_json TEXT NOT NULL,
    coefficients_json TEXT,
    metrics_json TEXT NOT NULL,
    caveats_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signal_prediction (
    validation_run_id INTEGER NOT NULL REFERENCES signal_validation_run(id) ON DELETE CASCADE,
    country_iso3 TEXT NOT NULL,
    sector_code TEXT NOT NULL,
    snapshot_year INTEGER NOT NULL,
    split TEXT NOT NULL,
    actual INTEGER NOT NULL,
    baseline_probability REAL NOT NULL,
    signal_probability REAL NOT NULL,
    PRIMARY KEY(validation_run_id, country_iso3, sector_code, snapshot_year)
);

CREATE INDEX IF NOT EXISTS idx_signal_event_panel
ON signal_event(country_iso3, sector_code, event_year);
CREATE INDEX IF NOT EXISTS idx_signal_panel_year
ON cooperation_signal_panel(snapshot_year, horizon_years);
"""


TIER_BY_EVENT = {
    "budget_approval": "A",
    "procurement": "A",
    "implementation_agreement": "A",
    "feasibility": "B",
    "mou": "B",
    "agreement": "B",
    "working_group": "B",
    "pilot": "B",
    "high_level_meeting": "C",
    "embassy_activity": "C",
    "press_mention": "C",
    "joint_project": "OUTCOME",
}

TIER_WEIGHT = {"A": 1.0, "B": 0.6, "C": 0.2, "OUTCOME": 0.0}

SIGNAL_FEATURE_NAMES = (
    "signal_weight_3y",
    "signal_trend",
    "tier_ab_count_3y",
    "source_diversity_3y",
    "partner_diversity_3y",
)

STRUCTURAL_FEATURE_NAMES = (
    "prior_project_count_3y",
    "years_since_last_project",
    "data_coverage",
)

FEATURE_NAMES = SIGNAL_FEATURE_NAMES + STRUCTURAL_FEATURE_NAMES
LOG_FEATURE_NAMES = {
    "signal_weight_3y",
    "tier_ab_count_3y",
    "source_diversity_3y",
    "partner_diversity_3y",
    "prior_project_count_3y",
}


def ensure_signal_schema(conn: sqlite3.Connection) -> None:
    ensure_project_history_schema(conn)
    conn.executescript(SIGNAL_SCHEMA)
    conn.commit()


def sync_signal_events(conn: sqlite3.Connection) -> dict[str, int]:
    """Normalize evidence and explicitly exclude realized projects from predictors."""
    ensure_signal_schema(conn)
    rows = conn.execute(
        """SELECT e.id, e.country_iso3, e.sector_code, e.event_type, e.event_date,
                  e.organizations_json, e.confidence, r.source_type, r.source_url
           FROM evidence e JOIN source_record r ON r.id=e.source_record_id
           WHERE e.event_date GLOB '[0-9][0-9][0-9][0-9]*'"""
    ).fetchall()
    counts = {"eligible": 0, "outcome_proxy": 0, "invalid_year": 0}
    for row in rows:
        try:
            event_year = int(str(row["event_date"])[:4])
        except ValueError:
            counts["invalid_year"] += 1
            continue
        tier = TIER_BY_EVENT.get(row["event_type"], "C")
        eligible = int(tier != "OUTCOME" and row["source_type"] in {"LOD", "MOFA"})
        signal_id = f"EVIDENCE-{row['id']}"
        conn.execute(
            """INSERT INTO signal_event(
                   signal_id, evidence_id, country_iso3, sector_code, event_type,
                   event_tier, event_year, source_type, confidence, base_weight,
                   organizations_json, source_url, eligible_predictor
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(signal_id) DO UPDATE SET
                 event_type=excluded.event_type, event_tier=excluded.event_tier,
                 event_year=excluded.event_year, source_type=excluded.source_type,
                 confidence=excluded.confidence, base_weight=excluded.base_weight,
                 organizations_json=excluded.organizations_json,
                 source_url=excluded.source_url,
                 eligible_predictor=excluded.eligible_predictor""",
            (
                signal_id,
                row["id"],
                row["country_iso3"],
                row["sector_code"],
                row["event_type"],
                tier,
                event_year,
                row["source_type"],
                float(row["confidence"]),
                TIER_WEIGHT[tier],
                row["organizations_json"],
                row["source_url"],
                eligible,
            ),
        )
        counts["eligible" if eligible else "outcome_proxy"] += 1
    conn.commit()
    return counts


def _organizations(rows: Iterable[sqlite3.Row]) -> set[str]:
    values: set[str] = set()
    for row in rows:
        try:
            items = json.loads(row["organizations_json"] or "[]")
        except json.JSONDecodeError:
            items = []
        for item in items:
            normalized = str(item).strip()
            if normalized:
                values.add(normalized)
    return values


def _project_outcome_filter(conn: sqlite3.Connection) -> str:
    """Return a SQL suffix that prevents OECD/KOICA double counting.

    OECD CRS is the cross-country outcome source used for validation. KOICA is
    retained in ``project_master`` as richer evidence, and becomes the fallback
    outcome source only when OECD CRS activities are absent.
    """
    has_oecd = bool(
        conn.execute(
            "SELECT EXISTS(SELECT 1 FROM project_master WHERE source_type='OECD_CRS')"
        ).fetchone()[0]
    )
    return " AND source_type<>'KOICA'" if has_oecd else ""


def build_signal_panel(
    conn: sqlite3.Connection,
    *,
    horizon_years: int = 2,
    start_year: int | None = None,
    outcome_cutoff_year: int | None = None,
    countries: Iterable[str] | None = None,
    sectors: Iterable[str] | None = None,
) -> dict[str, int]:
    """Create leakage-safe country-sector-year observations.

    Features only use events/projects at or before ``snapshot_year``. Outcomes
    only use projects in ``snapshot_year + 1 .. snapshot_year + horizon``.
    """
    if horizon_years < 1:
        raise ValueError("horizon_years must be at least 1")
    ensure_signal_schema(conn)
    project_counts = sync_internal_projects(conn)
    signal_counts = sync_signal_events(conn)
    outcome_filter = _project_outcome_filter(conn)

    source_years = [
        row[0]
        for row in conn.execute(
            f"""SELECT start_year FROM project_master
                WHERE is_new=1 {outcome_filter}
                UNION SELECT event_year FROM signal_event"""
        )
        if row[0] is not None
    ]
    if not source_years:
        return {"rows": 0, "positives": 0, **project_counts, **signal_counts}
    first_year = start_year if start_year is not None else min(source_years)
    latest_complete = min(max(source_years), date.today().year - 1)
    cutoff = outcome_cutoff_year if outcome_cutoff_year is not None else latest_complete
    last_snapshot = cutoff - horizon_years
    if last_snapshot < first_year:
        raise ValueError("Not enough historical years for the requested horizon")

    country_values = tuple(countries or [
        row[0] for row in conn.execute(
            f"""SELECT DISTINCT country_iso3 FROM project_master
                WHERE is_new=1 {outcome_filter} ORDER BY 1"""
        )
    ])
    sector_values = tuple(sectors or SECTORS.keys())
    conn.execute("DELETE FROM cooperation_signal_panel WHERE horizon_years=?", (horizon_years,))
    row_count = 0
    positives = 0

    for country in country_values:
        for sector in sector_values:
            all_projects = conn.execute(
                f"""SELECT start_year, COALESCE(commitment_amount, 0) AS amount
                   FROM project_master
                   WHERE country_iso3=? AND sector_code=? AND is_new=1
                     {outcome_filter}
                   ORDER BY start_year""",
                (country, sector),
            ).fetchall()
            project_years = [int(row["start_year"]) for row in all_projects]
            for snapshot_year in range(first_year, last_snapshot + 1):
                signal_rows = conn.execute(
                    """SELECT event_year, event_tier, source_type, confidence, base_weight,
                              organizations_json
                       FROM signal_event
                       WHERE country_iso3=? AND sector_code=? AND eligible_predictor=1
                         AND event_year BETWEEN ? AND ?""",
                    (country, sector, snapshot_year - 2, snapshot_year),
                ).fetchall()
                current_count = sum(1 for row in signal_rows if row["event_year"] == snapshot_year)
                previous_count = len(signal_rows) - current_count
                weighted_signal = sum(
                    float(row["confidence"])
                    * float(row["base_weight"])
                    * (0.65 ** (snapshot_year - int(row["event_year"])))
                    for row in signal_rows
                )
                prior_3 = sum(snapshot_year - 2 <= year <= snapshot_year for year in project_years)
                prior_5 = sum(snapshot_year - 4 <= year <= snapshot_year for year in project_years)
                prior_years = [year for year in project_years if year <= snapshot_year]
                years_since = min(10, snapshot_year - max(prior_years)) if prior_years else 10
                outcome_rows = [
                    row for row in all_projects
                    if snapshot_year < int(row["start_year"]) <= snapshot_year + horizon_years
                ]
                outcome_count = len(outcome_rows)
                outcome = int(outcome_count > 0)
                sources = {str(row["source_type"]) for row in signal_rows}
                coverage_sources = set(sources)
                if prior_5:
                    coverage_sources.add("PROJECT_HISTORY")
                coverage = min(1.0, len(coverage_sources) / 3.0)
                conn.execute(
                    """INSERT INTO cooperation_signal_panel(
                           country_iso3, sector_code, snapshot_year, horizon_years,
                           signal_count_1y, signal_count_3y, signal_weight_3y,
                           signal_trend, tier_ab_count_3y, source_diversity_3y,
                           partner_diversity_3y, prior_project_count_3y,
                           prior_project_count_5y, years_since_last_project,
                           data_coverage, outcome_new_project, outcome_project_count,
                           outcome_commitment
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        country,
                        sector,
                        snapshot_year,
                        horizon_years,
                        current_count,
                        len(signal_rows),
                        weighted_signal,
                        current_count - previous_count / 2.0,
                        sum(row["event_tier"] in {"A", "B"} for row in signal_rows),
                        len(sources),
                        len(_organizations(signal_rows)),
                        prior_3,
                        prior_5,
                        years_since,
                        coverage,
                        outcome,
                        outcome_count,
                        sum(float(row["amount"]) for row in outcome_rows),
                    ),
                )
                row_count += 1
                positives += outcome
    conn.commit()
    return {
        "rows": row_count,
        "positives": positives,
        "first_snapshot_year": first_year,
        "last_snapshot_year": last_snapshot,
        **{f"projects_{key.lower()}": value for key, value in project_counts.items()},
        **{f"signals_{key}": value for key, value in signal_counts.items()},
    }


def _wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return max(0.0, center - spread), min(1.0, center + spread)


def _feature_value(row: dict, name: str) -> float:
    value = float(row[name])
    return math.log1p(max(0.0, value)) if name in LOG_FEATURE_NAMES else value


def _standardize(rows: list[dict], feature_names: tuple[str, ...], means=None, scales=None):
    if means is None:
        means = {
            name: sum(_feature_value(row, name) for row in rows) / len(rows)
            for name in feature_names
        }
    if scales is None:
        scales = {}
        for name in feature_names:
            variance = sum(
                (_feature_value(row, name) - means[name]) ** 2 for row in rows
            ) / max(1, len(rows) - 1)
            scales[name] = math.sqrt(variance) or 1.0
    values = [
        [1.0] + [
            (_feature_value(row, name) - means[name]) / scales[name]
            for name in feature_names
        ]
        for row in rows
    ]
    return values, means, scales


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-min(value, 35))
        return 1 / (1 + z)
    z = math.exp(max(value, -35))
    return z / (1 + z)


def _fit_logistic(
    x: list[list[float]],
    y: list[int],
    *,
    l2: float = 1.0,
    learning_rate: float = 0.08,
    iterations: int = 4000,
) -> list[float]:
    coefficients = [0.0] * len(x[0])
    for step in range(iterations):
        gradients = [0.0] * len(coefficients)
        for values, actual in zip(x, y):
            predicted = _sigmoid(sum(beta * value for beta, value in zip(coefficients, values)))
            error = predicted - actual
            for index, value in enumerate(values):
                gradients[index] += error * value
        for index in range(1, len(coefficients)):
            gradients[index] += l2 * coefficients[index]
        rate = learning_rate / math.sqrt(1 + step / 500)
        for index in range(len(coefficients)):
            coefficients[index] -= rate * gradients[index] / len(x)
    return coefficients


def _predict(x: list[list[float]], coefficients: list[float]) -> list[float]:
    return [_sigmoid(sum(beta * value for beta, value in zip(coefficients, row))) for row in x]


def _brier(actual: list[int], predicted: list[float]) -> float:
    return sum((y - p) ** 2 for y, p in zip(actual, predicted)) / len(actual)


def _average_precision(actual: list[int], predicted: list[float]) -> float:
    positives = sum(actual)
    if positives == 0:
        return 0.0
    grouped: dict[float, list[int]] = defaultdict(list)
    for probability, value in zip(predicted, actual):
        grouped[round(float(probability), 12)].append(value)
    true_seen = 0
    observations_seen = 0
    area = 0.0
    for probability in sorted(grouped, reverse=True):
        values = grouped[probability]
        group_positives = sum(values)
        true_seen += group_positives
        observations_seen += len(values)
        area += (group_positives / positives) * (true_seen / observations_seen)
    return area


def _top_lift(actual: list[int], predicted: list[float], fraction: float = 0.1) -> tuple[float, float]:
    count = max(1, math.ceil(len(actual) * fraction))
    ordered_scores = sorted((float(value) for value in predicted), reverse=True)
    threshold = ordered_scores[count - 1]
    top = [
        value for value, probability in zip(actual, predicted)
        if float(probability) >= threshold
    ]
    top_rate = sum(top) / len(top)
    base_rate = sum(actual) / len(actual)
    return top_rate, top_rate / base_rate if base_rate else 0.0


def _baseline_probabilities(train: list[dict], test: list[dict], strength: float = 5.0) -> list[float]:
    global_rate = sum(row["outcome_new_project"] for row in train) / len(train)
    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row in train:
        grouped[(row["country_iso3"], row["sector_code"])].append(row["outcome_new_project"])
    result = []
    for row in test:
        values = grouped.get((row["country_iso3"], row["sector_code"]), [])
        result.append((sum(values) + strength * global_rate) / (len(values) + strength))
    return result


def validate_signals(
    conn: sqlite3.Connection,
    *,
    horizon_years: int = 2,
    test_start_year: int | None = None,
) -> dict:
    """Validate candidate signals with a chronological holdout.

    The model is deliberately small and interpretable. If there are fewer than
    20 positive training events it only returns descriptive association metrics.
    """
    ensure_signal_schema(conn)
    rows = [
        dict(row)
        for row in conn.execute(
            """SELECT * FROM cooperation_signal_panel
               WHERE horizon_years=? ORDER BY snapshot_year, country_iso3, sector_code""",
            (horizon_years,),
        )
    ]
    if not rows:
        raise ValueError("Signal panel is empty; run build_signal_panel first")
    years = sorted({row["snapshot_year"] for row in rows})
    split_year = test_start_year if test_start_year is not None else years[max(1, int(len(years) * 0.8))]
    train = [row for row in rows if row["snapshot_year"] < split_year]
    test = [row for row in rows if row["snapshot_year"] >= split_year]
    if not train or not test:
        raise ValueError("Chronological split produced an empty train or test set")

    signal_rows = [row for row in rows if row["signal_weight_3y"] > 0]
    no_signal_rows = [row for row in rows if row["signal_weight_3y"] <= 0]
    signal_positive = sum(row["outcome_new_project"] for row in signal_rows)
    no_signal_positive = sum(row["outcome_new_project"] for row in no_signal_rows)
    signal_rate = signal_positive / len(signal_rows) if signal_rows else 0.0
    no_signal_rate = no_signal_positive / len(no_signal_rows) if no_signal_rows else 0.0
    association = {
        "signal_n": len(signal_rows),
        "signal_positive": signal_positive,
        "signal_rate": signal_rate,
        "signal_rate_ci95": _wilson(signal_positive, len(signal_rows)),
        "no_signal_n": len(no_signal_rows),
        "no_signal_positive": no_signal_positive,
        "no_signal_rate": no_signal_rate,
        "no_signal_rate_ci95": _wilson(no_signal_positive, len(no_signal_rows)),
        "risk_difference": signal_rate - no_signal_rate,
        "lift": signal_rate / no_signal_rate if no_signal_rate else None,
    }

    caveats = []
    status = "validated"
    train_positive = sum(row["outcome_new_project"] for row in train)
    test_positive = sum(row["outcome_new_project"] for row in test)
    metrics: dict[str, object] = {
        "association": association,
        "train_rows": len(train),
        "test_rows": len(test),
        "train_positives": train_positive,
        "test_positives": test_positive,
    }
    coefficients_json = None
    predictions: list[tuple[dict, float, float]] = []

    if train_positive < 20 or test_positive < 5:
        status = "descriptive_only"
        caveats.append("Too few positive events for a stable chronological predictive validation.")
    else:
        y_train = [int(row["outcome_new_project"]) for row in train]
        y_test = [int(row["outcome_new_project"]) for row in test]

        structural_x_train, structural_means, structural_scales = _standardize(
            train, STRUCTURAL_FEATURE_NAMES
        )
        structural_x_test, _, _ = _standardize(
            test, STRUCTURAL_FEATURE_NAMES, structural_means, structural_scales
        )
        structural_coefficients = _fit_logistic(structural_x_train, y_train)
        structural_probabilities = _predict(structural_x_test, structural_coefficients)

        signal_x_train, signal_means, signal_scales = _standardize(train, FEATURE_NAMES)
        signal_x_test, _, _ = _standardize(test, FEATURE_NAMES, signal_means, signal_scales)
        signal_coefficients = _fit_logistic(signal_x_train, y_train)
        signal_probabilities = _predict(signal_x_test, signal_coefficients)

        historical_probabilities = _baseline_probabilities(train, test)
        global_rate = sum(y_train) / len(y_train)
        global_probabilities = [global_rate] * len(y_test)
        top_rate, lift = _top_lift(y_test, signal_probabilities)
        signal_brier = _brier(y_test, signal_probabilities)
        structural_brier = _brier(y_test, structural_probabilities)
        historical_brier = _brier(y_test, historical_probabilities)
        global_brier = _brier(y_test, global_probabilities)
        signal_ap = _average_precision(y_test, signal_probabilities)
        structural_ap = _average_precision(y_test, structural_probabilities)
        historical_ap = _average_precision(y_test, historical_probabilities)
        global_ap = _average_precision(y_test, global_probabilities)
        incremental_brier = (
            (structural_brier - signal_brier) / structural_brier if structural_brier else 0.0
        )
        historical_improvement = (
            (global_brier - historical_brier) / global_brier if global_brier else 0.0
        )
        structural_improvement = (
            (global_brier - structural_brier) / global_brier if global_brier else 0.0
        )
        metrics.update(
            {
                "signal_brier": signal_brier,
                "structural_brier": structural_brier,
                "historical_rate_brier": historical_brier,
                "global_constant_brier": global_brier,
                "historical_rate_brier_improvement_vs_global": historical_improvement,
                "structural_brier_improvement_vs_global": structural_improvement,
                "signal_brier_improvement_vs_structural": incremental_brier,
                "signal_average_precision": signal_ap,
                "structural_average_precision": structural_ap,
                "historical_rate_average_precision": historical_ap,
                "global_constant_average_precision": global_ap,
                "precision_top_10pct": top_rate,
                "lift_top_10pct": lift,
            }
        )
        coefficients_json = {
            "signal_model": {
                "intercept": signal_coefficients[0],
                **{
                    name: signal_coefficients[index + 1]
                    for index, name in enumerate(FEATURE_NAMES)
                },
                "means": signal_means,
                "scales": signal_scales,
            },
            "structural_model": {
                "intercept": structural_coefficients[0],
                **{
                    name: structural_coefficients[index + 1]
                    for index, name in enumerate(STRUCTURAL_FEATURE_NAMES)
                },
                "means": structural_means,
                "scales": structural_scales,
            },
        }
        predictions = list(zip(test, structural_probabilities, signal_probabilities))
        if incremental_brier <= 0.01 or signal_ap < structural_ap:
            structural_supported = (
                structural_improvement >= 0.05
                and structural_ap >= global_ap * 1.10
            )
            status = "structural_only" if structural_supported else "not_supported"
            caveats.append(
                "Diplomatic signal features did not add stable predictive value over the "
                "prior-project/readiness model."
            )
        if lift < 1.5:
            caveats.append("Top-decile lift is below the provisional 1.5x usefulness threshold.")

    country_count = len({row["country_iso3"] for row in rows})
    if country_count < 10:
        caveats.append(
            f"Only {country_count} countries are available; results are not externally generalizable."
        )
    source_counts = dict(
        conn.execute("SELECT source_type, COUNT(*) FROM project_master GROUP BY source_type").fetchall()
    )
    outcome_filter = _project_outcome_filter(conn)
    outcome_source_counts = dict(
        conn.execute(
            f"""SELECT source_type, COUNT(*) FROM project_master
                WHERE is_new=1 {outcome_filter} GROUP BY source_type"""
        ).fetchall()
    )
    if source_counts.get("KOICA") and source_counts.get("OECD_CRS"):
        caveats.append(
            "KOICA projects are retained as evidence but excluded from outcome counts "
            "because OECD CRS is the authoritative ODA outcome source and cross-source "
            "record linkage is not yet complete."
        )
    if not source_counts.get("KOICA") and not source_counts.get("OECD_CRS"):
        caveats.append(
            "Outcome labels currently contain KF public-diplomacy projects only; KOICA/OECD ODA labels are absent."
        )

    created_at = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """INSERT INTO signal_validation_run(
               created_at, horizon_years, train_end_year, test_start_year, status,
               row_count, positive_count, feature_names_json, coefficients_json,
               metrics_json, caveats_json
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            created_at,
            horizon_years,
            split_year - 1,
            split_year,
            status,
            len(rows),
            sum(row["outcome_new_project"] for row in rows),
            json.dumps(FEATURE_NAMES),
            json.dumps(coefficients_json, ensure_ascii=False) if coefficients_json else None,
            json.dumps(metrics, ensure_ascii=False),
            json.dumps(caveats, ensure_ascii=False),
        ),
    )
    run_id = int(cursor.lastrowid)
    for row, baseline, signal in predictions:
        conn.execute(
            """INSERT INTO signal_prediction(
                   validation_run_id, country_iso3, sector_code, snapshot_year,
                   split, actual, baseline_probability, signal_probability
               ) VALUES (?, ?, ?, ?, 'test', ?, ?, ?)""",
            (
                run_id,
                row["country_iso3"],
                row["sector_code"],
                row["snapshot_year"],
                row["outcome_new_project"],
                baseline,
                signal,
            ),
        )
    conn.commit()
    return {
        "run_id": run_id,
        "status": status,
        "horizon_years": horizon_years,
        "test_start_year": split_year,
        "project_sources": source_counts,
        "outcome_project_sources": outcome_source_counts,
        "metrics": metrics,
        "coefficients": coefficients_json,
        "caveats": caveats,
    }


def _model_probability(feature_row: dict, model: dict, feature_names: tuple[str, ...]) -> float:
    value = float(model["intercept"])
    means = model["means"]
    scales = model["scales"]
    for name in feature_names:
        standardized = (
            _feature_value(feature_row, name) - float(means[name])
        ) / float(scales[name])
        value += float(model[name]) * standardized
    return _sigmoid(value)


def predict_current_candidates(
    conn: sqlite3.Connection,
    *,
    horizon_years: int = 2,
    snapshot_year: int | None = None,
    countries: Iterable[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    """Score the current snapshot only after signals pass temporal validation."""
    row = conn.execute(
        """SELECT id, status, coefficients_json FROM signal_validation_run
           WHERE horizon_years=? ORDER BY id DESC LIMIT 1""",
        (horizon_years,),
    ).fetchone()
    if (
        not row
        or row["status"] not in {"validated", "structural_only"}
        or not row["coefficients_json"]
    ):
        return []
    model = json.loads(row["coefficients_json"])
    signal_model = model["signal_model"]
    structural_model = model["structural_model"]
    target_year = snapshot_year or date.today().year
    available_countries = [
        item[0]
        for item in conn.execute(
            """SELECT DISTINCT country_iso3 FROM cooperation_signal_panel
               WHERE horizon_years=? ORDER BY country_iso3""",
            (horizon_years,),
        )
    ]
    selected_countries = (
        [value.upper() for value in countries]
        if countries is not None else available_countries
    )
    names = {
        item["iso3"]: item["name_ko"]
        for item in conn.execute("SELECT iso3, name_ko FROM country")
    }
    sector_names = {
        item["code"]: item["name_ko"]
        for item in conn.execute("SELECT code, name_ko FROM sector WHERE enabled=1")
    }
    outcome_filter = _project_outcome_filter(conn)
    candidates: list[dict] = []
    panel_rows = conn.execute(
        """SELECT country_iso3, sector_code, outcome_new_project
           FROM cooperation_signal_panel WHERE horizon_years=?""",
        (horizon_years,),
    ).fetchall()
    global_recurrence = (
        sum(int(item["outcome_new_project"]) for item in panel_rows) / len(panel_rows)
        if panel_rows else 0.0
    )
    recurrence_groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for item in panel_rows:
        recurrence_groups[(item["country_iso3"], item["sector_code"])].append(
            int(item["outcome_new_project"])
        )
    for country in selected_countries:
        for sector in SECTORS:
            signal_rows = conn.execute(
                """SELECT event_year, event_tier, source_type, confidence, base_weight,
                          organizations_json
                   FROM signal_event
                   WHERE country_iso3=? AND sector_code=? AND eligible_predictor=1
                     AND event_year BETWEEN ? AND ?""",
                (country, sector, target_year - 2, target_year),
            ).fetchall()
            current_count = sum(1 for item in signal_rows if item["event_year"] == target_year)
            previous_count = len(signal_rows) - current_count
            weighted_signal = sum(
                float(item["confidence"])
                * float(item["base_weight"])
                * (0.65 ** (target_year - int(item["event_year"])))
                for item in signal_rows
            )
            project_rows = conn.execute(
                f"""SELECT start_year FROM project_master
                   WHERE country_iso3=? AND sector_code=? AND is_new=1
                     {outcome_filter}
                     AND start_year<=? ORDER BY start_year""",
                (country, sector, target_year),
            ).fetchall()
            project_years = [int(item["start_year"]) for item in project_rows]
            prior_3 = sum(target_year - 2 <= year <= target_year for year in project_years)
            sources = {str(item["source_type"]) for item in signal_rows}
            coverage_sources = set(sources)
            if any(target_year - 4 <= year <= target_year for year in project_years):
                coverage_sources.add("PROJECT_HISTORY")
            features = {
                "signal_weight_3y": weighted_signal,
                "signal_trend": current_count - previous_count / 2.0,
                "tier_ab_count_3y": sum(
                    item["event_tier"] in {"A", "B"} for item in signal_rows
                ),
                "source_diversity_3y": len(sources),
                "partner_diversity_3y": len(_organizations(signal_rows)),
                "prior_project_count_3y": prior_3,
                "years_since_last_project": (
                    min(10, target_year - max(project_years)) if project_years else 10
                ),
                "data_coverage": min(1.0, len(coverage_sources) / 3.0),
            }
            structural_probability = _model_probability(
                features, structural_model, STRUCTURAL_FEATURE_NAMES
            )
            signal_probability = _model_probability(features, signal_model, FEATURE_NAMES)
            recurrence_values = recurrence_groups.get((country, sector), [])
            recurrence_probability = (
                (sum(recurrence_values) + 5.0 * global_recurrence)
                / (len(recurrence_values) + 5.0)
            )
            diplomatic_validated = row["status"] == "validated"
            candidates.append(
                {
                    "validation_run_id": int(row["id"]),
                    "snapshot_year": target_year,
                    "horizon_years": horizon_years,
                    "country_iso3": country,
                    "country_name_ko": names.get(country, country),
                    "sector_code": sector,
                    "sector_name_ko": sector_names.get(sector, sector),
                    "validated_signal_type": (
                        "diplomatic_plus_recurrence"
                        if diplomatic_validated else "project_momentum"
                    ),
                    "recommended_probability": (
                        signal_probability if diplomatic_validated else structural_probability
                    ),
                    "historical_recurrence_probability": recurrence_probability,
                    "structural_probability": structural_probability,
                    "diplomatic_signal_probability": (
                        signal_probability if diplomatic_validated else None
                    ),
                    "diplomatic_signal_increment": (
                        signal_probability - structural_probability
                        if diplomatic_validated else None
                    ),
                    **features,
                }
            )
    candidates.sort(
        key=lambda item: (
            item["recommended_probability"],
            item["structural_probability"],
        ),
        reverse=True,
    )
    return candidates[:limit]
