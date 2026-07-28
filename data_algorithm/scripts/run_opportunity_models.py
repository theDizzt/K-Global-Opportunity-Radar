from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.opportunity_models import (
    collect_world_bank_bulk_need_indicators,
    collect_world_bank_need_indicators,
    run_opportunity_models,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run separated opportunity models without forcing a total score"
    )
    parser.add_argument("--db", default="data/statistical_signals_full.db")
    parser.add_argument(
        "--country",
        action="append",
        dest="countries",
        help="ISO3 country; repeat as needed (default: VNM, IDN, MNG)",
    )
    parser.add_argument("--snapshot-year", type=int)
    parser.add_argument("--horizon", type=int, default=2)
    parser.add_argument(
        "--fetch-world-bank",
        action="store_true",
        help="Fetch multi-indicator education, digital and health data before scoring",
    )
    parser.add_argument(
        "--world-bank-scope",
        choices=("crs", "candidates"),
        default="crs",
        help=(
            "Countries used to build need percentiles: all OECD CRS recipients "
            "(default) or only candidate countries"
        ),
    )
    parser.add_argument("--request-interval", type=float, default=1.0)
    parser.add_argument("--world-bank-batch-size", type=int, default=40)
    parser.add_argument("--world-bank-timeout", type=float, default=60.0)
    parser.add_argument(
        "--world-bank-transport",
        choices=("bulk", "batch", "all"),
        default="bulk",
        help=(
            "Use one zipped CSV per indicator (default), filtered JSON batches, "
            "or the JSON country/all endpoint"
        ),
    )
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    countries = args.countries or ["VNM", "IDN", "MNG"]
    conn = connect(args.db)
    initialize(conn)
    collection = None
    if args.fetch_world_bank:
        indicator_countries = countries
        if args.world_bank_scope == "crs":
            indicator_countries = [
                str(row[0])
                for row in conn.execute(
                    """SELECT DISTINCT recipient_iso3
                       FROM donor_activity_aggregate
                       ORDER BY recipient_iso3"""
                )
            ] or countries
        if args.world_bank_transport == "bulk":
            collection = collect_world_bank_bulk_need_indicators(
                conn,
                countries=indicator_countries,
                end_year=args.snapshot_year,
                request_interval_seconds=args.request_interval,
                timeout_seconds=args.world_bank_timeout,
            )
        else:
            collection = collect_world_bank_need_indicators(
                conn,
                countries=indicator_countries,
                end_year=args.snapshot_year,
                request_interval_seconds=args.request_interval,
                country_batch_size=args.world_bank_batch_size,
                timeout_seconds=args.world_bank_timeout,
                use_all_countries_endpoint=(
                    args.world_bank_transport == "all"
                ),
            )
    models = run_opportunity_models(
        conn,
        countries=countries,
        snapshot_year=args.snapshot_year,
        horizon_years=args.horizon,
    )
    result = {"collection": collection, **models}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    conn.close()


if __name__ == "__main__":
    main()
