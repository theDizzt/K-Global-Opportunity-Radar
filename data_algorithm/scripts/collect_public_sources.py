from __future__ import annotations

import argparse
import json

from opportunity_radar.config import load_env
from opportunity_radar.db import connect, initialize
from opportunity_radar.kf_pipeline import KfCollector
from opportunity_radar.mofa_lod import MofaLodCollector
from opportunity_radar.mofa_pipeline import MofaCollector
from opportunity_radar.settings import public_data_service_key


parser = argparse.ArgumentParser(description="Collect KF, MOFA REST, and MOFA LOD data")
parser.add_argument("--db", default="data/radar.db")
parser.add_argument(
    "--sources", nargs="+", choices=("kf", "mofa", "lod"),
    default=("kf", "mofa", "lod"),
)
parser.add_argument("--page-size", type=int, default=200)
parser.add_argument("--max-pages", type=int, default=10)
args = parser.parse_args()

load_env()
conn = connect(args.db)
initialize(conn)
results = {}
try:
    if "kf" in args.sources:
        results["KF"] = KfCollector(conn, public_data_service_key()).collect(
            page_size=args.page_size, max_pages=args.max_pages
        )
    if "mofa" in args.sources:
        results["MOFA"] = MofaCollector(conn, public_data_service_key()).collect(
            page_size=args.page_size, max_pages=args.max_pages
        )
    if "lod" in args.sources:
        results["LOD"] = MofaLodCollector(conn).collect(
            page_size=min(args.page_size, 200), max_pages=args.max_pages
        )
    print(json.dumps(results, ensure_ascii=False, indent=2))
finally:
    conn.close()
