from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .config import load_env
from .db import connect, initialize
from .explain import LlmExplainer, build_explanation_context
from .ingest import load_demo_bundle
from .scoring import WEIGHT_PRESETS, calculate_scores, recommend_with_options, recommendations


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="K-Global Opportunity Radar MVP")
    p.add_argument("--db", default="data/radar.db", help="SQLite database path")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    load = sub.add_parser("load-demo")
    load.add_argument("--bundle", default="data/demo_bundle.json")
    score = sub.add_parser("score")
    score.add_argument("--as-of", default=date.today().isoformat())
    rec = sub.add_parser("recommend")
    rec.add_argument("--sector", required=True)
    rec.add_argument("--limit", type=int, default=3)
    rec.add_argument("--explain", action="store_true")
    rec.add_argument("--region")
    rec.add_argument("--country")
    rec.add_argument("--max-risk", type=int)
    rec.add_argument("--min-confidence", type=float, default=0)
    rec.add_argument("--preset", choices=sorted(WEIGHT_PRESETS))
    rec.add_argument("--weights", help="JSON object with demand/alignment/readiness/korea_base")
    demo = sub.add_parser("run-demo")
    demo.add_argument("--bundle", default="data/demo_bundle.json")
    demo.add_argument("--sector", default="education")
    return p


def main(argv: list[str] | None = None) -> int:
    load_env()
    args = _parser().parse_args(argv)
    conn = connect(args.db)
    initialize(conn)
    if args.command == "init-db":
        print(f"initialized: {Path(args.db)}")
    elif args.command == "load-demo":
        load_demo_bundle(conn, args.bundle)
        print("demo data loaded")
    elif args.command == "score":
        count = calculate_scores(conn, date.fromisoformat(args.as_of))
        print(f"score snapshots written: {count}")
    elif args.command == "recommend":
        custom_weights = json.loads(args.weights) if args.weights else None
        if args.preset:
            custom_weights = WEIGHT_PRESETS[args.preset]
        rows = recommend_with_options(
            conn, args.sector, args.limit,
            region=args.region,
            country_iso3=args.country,
            max_risk=args.max_risk,
            min_confidence=args.min_confidence,
            weights=custom_weights,
        )
        if args.explain:
            explainer = LlmExplainer()
            for row in rows:
                row["explanation"] = explainer.explain(build_explanation_context(conn, row["id"]))
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif args.command == "run-demo":
        load_demo_bundle(conn, args.bundle)
        calculate_scores(conn, date(2026, 7, 16))
        rows = recommendations(conn, args.sector, 3)
        explainer = LlmExplainer()
        for row in rows:
            row["explanation"] = explainer.explain(build_explanation_context(conn, row["id"]))
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
