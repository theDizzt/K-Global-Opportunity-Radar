from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.statistical_signals import (
    build_signal_panel,
    predict_current_candidates,
    validate_signals,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and validate cooperation signals")
    parser.add_argument("--db", default="data/statistical_signals.db")
    parser.add_argument("--horizon", type=int, default=2)
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--outcome-cutoff-year", type=int)
    parser.add_argument("--test-start-year", type=int)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--candidate-country",
        action="append",
        help="ISO3 candidate country; repeat to limit current predictions",
    )
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    conn = connect(args.db)
    initialize(conn)
    build = build_signal_panel(
        conn,
        horizon_years=args.horizon,
        start_year=args.start_year,
        outcome_cutoff_year=args.outcome_cutoff_year,
    )
    validation = validate_signals(
        conn,
        horizon_years=args.horizon,
        test_start_year=args.test_start_year,
    )
    candidates = predict_current_candidates(
        conn,
        horizon_years=args.horizon,
        countries=args.candidate_country,
        limit=args.limit,
    )
    result = {"build": build, "validation": validation, "candidates": candidates}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    conn.close()


if __name__ == "__main__":
    main()
