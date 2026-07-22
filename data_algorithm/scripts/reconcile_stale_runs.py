from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone


parser = argparse.ArgumentParser(description="Mark orphaned ingestion runs as interrupted")
parser.add_argument("--db", default="data/radar_real.db")
parser.add_argument("--source", default="KOICA")
args = parser.parse_args()
conn = sqlite3.connect(args.db)
cursor = conn.execute(
    """UPDATE ingestion_run
       SET finished_at=?, status='interrupted',
           error_message=COALESCE(error_message, 'Operator interrupted after repeated slice timeouts')
       WHERE source_type=? AND status='running'""",
    (datetime.now(timezone.utc).isoformat(), args.source),
)
conn.commit()
print(f"reconciled={cursor.rowcount}")
