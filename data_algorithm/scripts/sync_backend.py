from __future__ import annotations

import argparse

from opportunity_radar.backend_sync import sync_backend


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync calculated opportunity scores and evidence to the FastAPI backend."
    )
    parser.add_argument("--algorithm-db", default="data/radar.db")
    parser.add_argument("--backend-db", default="../data/k_global_radar.db")
    parser.add_argument("--as-of")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Mark synchronized score snapshots as demo data.",
    )
    args = parser.parse_args()
    result = sync_backend(
        args.algorithm_db,
        args.backend_db,
        as_of_date=args.as_of,
        is_demo=args.demo,
    )
    print(
        "Backend sync complete: "
        f"scores={result.scores}, documents={result.documents}, "
        f"skipped_scores={result.skipped_scores}, "
        f"skipped_documents={result.skipped_documents}"
    )


if __name__ == "__main__":
    main()
