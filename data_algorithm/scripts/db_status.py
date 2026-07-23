from __future__ import annotations

import argparse
import json
import sqlite3


parser = argparse.ArgumentParser()
parser.add_argument("--db", default="data/radar_real.db")
args = parser.parse_args()
conn = sqlite3.connect(args.db)
conn.row_factory = sqlite3.Row
latest = conn.execute(
    """SELECT id, source_type, started_at, finished_at, status, record_count, error_message
       FROM ingestion_run ORDER BY id DESC LIMIT 1"""
).fetchone()
counts = dict(conn.execute("SELECT country_iso3, COUNT(*) FROM project GROUP BY country_iso3"))
raw_count = conn.execute(
    "SELECT COUNT(*) FROM raw_api_response WHERE run_id=?", (latest["id"],)
).fetchone()[0] if latest else 0
issue_count = conn.execute(
    "SELECT COUNT(*) FROM data_quality_issue WHERE source_type='KOICA' AND status='open'"
).fetchone()[0]
print(json.dumps({"latest_run": dict(latest) if latest else None, "project_counts": counts,
                  "latest_raw_responses": raw_count, "open_koica_issues": issue_count}, ensure_ascii=False, indent=2))
