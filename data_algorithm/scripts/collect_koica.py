from __future__ import annotations

import argparse
import json
import os
from datetime import date

from opportunity_radar.config import load_env, require_setting
from opportunity_radar.db import connect, initialize
from opportunity_radar.koica_pipeline import PROJECT_TYPES
from opportunity_radar.resilient_koica import ResilientKoicaCollector


parser = argparse.ArgumentParser(description="Collect KOICA projects for Vietnam, Indonesia, and Mongolia")
parser.add_argument("--db", default=None)
parser.add_argument("--from-year", type=int, default=1991)
parser.add_argument("--to-year", type=int, default=date.today().year)
parser.add_argument("--page-size", type=int, default=10)
parser.add_argument("--project-type", action="append", help="Repeat to collect selected KOICA project types")
parser.add_argument("--min-request-interval", type=float, default=3.0)
parser.add_argument("--max-retries", type=int, default=3)
args = parser.parse_args()

load_env()
db_path = args.db or os.getenv("RADAR_DB_PATH", "data/radar_real.db")
conn = connect(db_path)
initialize(conn)
collector = ResilientKoicaCollector(
    conn,
    require_setting("KOICA_SERVICE_KEY"),
    min_request_interval=args.min_request_interval,
    max_retries=args.max_retries,
)
counts = collector.collect(
    years=range(args.from_year, args.to_year + 1),
    page_size=args.page_size,
    project_types=tuple(args.project_type) if args.project_type else PROJECT_TYPES,
)
print(json.dumps({"database": db_path, "countries": counts, "total": sum(counts.values())}, ensure_ascii=False, indent=2))
conn.close()
