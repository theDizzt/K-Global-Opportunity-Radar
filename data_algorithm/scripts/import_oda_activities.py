from __future__ import annotations

import argparse
import json

from opportunity_radar.db import connect, initialize
from opportunity_radar.project_history import load_activity_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Import OECD CRS-style Korean ODA activities")
    parser.add_argument("path")
    parser.add_argument("--db", default="data/statistical_signals.db")
    parser.add_argument("--country-map")
    parser.add_argument("--delimiter")
    parser.add_argument("--source-type", default="OECD_CRS")
    parser.add_argument("--source-url")
    parser.add_argument("--all-donors", action="store_true")
    args = parser.parse_args()

    conn = connect(args.db)
    initialize(conn)
    result = load_activity_file(
        conn,
        args.path,
        source_type=args.source_type,
        country_map_path=args.country_map,
        delimiter=args.delimiter,
        korea_only=not args.all_donors,
        source_url=args.source_url,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    conn.close()


if __name__ == "__main__":
    main()
