from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.donor_supply import load_all_donor_crs_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate OECD CRS files by donor, recipient, sector and year"
    )
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--db", default="data/statistical_signals_full.db")
    parser.add_argument(
        "--recipient",
        action="append",
        help="Optional ISO3 filter; omit to build global comparison percentiles",
    )
    args = parser.parse_args()

    conn = connect(args.db)
    initialize(conn)
    results = []
    for raw_path in args.paths:
        path = Path(raw_path)
        year = next(
            (part for part in path.stem.split() if part.isdigit() and len(part) == 4),
            None,
        )
        source_url = (
            "https://webfs-dcd.oecd.org/files/dotStat/DSD_CRS/"
            f"CRS%20{year}%20data.zip"
            if year else None
        )
        results.append(
            load_all_donor_crs_file(
                conn,
                path,
                source_url=source_url,
                recipient_filter=args.recipient,
            )
        )
        print(json.dumps(results[-1], ensure_ascii=False))
    print(json.dumps({"files": results}, ensure_ascii=False, indent=2))
    conn.close()


if __name__ == "__main__":
    main()
