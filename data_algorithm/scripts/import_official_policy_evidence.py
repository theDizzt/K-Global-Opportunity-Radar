from __future__ import annotations

import argparse
import json
import sys

from opportunity_radar.curated_policy import load_curated_policy_evidence
from opportunity_radar.db import connect, initialize


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import source-verified official Tier A/B policy evidence"
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="data/policy/official_policy_evidence.json",
    )
    parser.add_argument("--db", default="data/statistical_signals_full.db")
    args = parser.parse_args()

    conn = connect(args.db)
    initialize(conn)
    result = load_curated_policy_evidence(conn, args.source)
    conn.close()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
