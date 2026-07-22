from __future__ import annotations

import argparse
import json

from opportunity_radar.db import connect, initialize
from opportunity_radar.kf_studies import load_kf_academic_html


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the official KF Korean-studies export")
    parser.add_argument("--db", default="data/radar_real.db")
    parser.add_argument("--input", default="data/raw/kf_korean_studies.xlsx")
    args = parser.parse_args()
    conn = connect(args.db)
    initialize(conn)
    counts = load_kf_academic_html(conn, args.input)
    initialize(conn)
    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
