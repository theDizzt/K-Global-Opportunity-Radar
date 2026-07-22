from __future__ import annotations

import argparse
import json

from opportunity_radar.db import connect, initialize
from opportunity_radar.reporting import generate_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate clean datasets and validation artifacts")
    parser.add_argument("--db", default="data/radar_real.db")
    parser.add_argument("--output", default="outputs")
    parser.add_argument("--as-of", default="2026-07-21")
    args = parser.parse_args()
    conn = connect(args.db)
    initialize(conn)
    print(json.dumps(generate_outputs(conn, args.output, args.as_of), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
