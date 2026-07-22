import argparse
import csv
import json
from pathlib import Path

from backend.database.connection import get_connection
from config.constants import (
    EVIDENCE,
    PROJECTS,
    SIGNAL_HISTORY,
    SOURCE_DESCRIPTIONS,
    SOURCE_LINKS,
)
from config.settings import DATABASE_PATH, DATA_PATH


SCHEMA_PATH = Path(__file__).with_name("schema.sql")
INDICATOR_CODES = ("diplomacy", "oda", "korean_base", "people_exchange", "esg")
SOURCE_SEEDS = {
    "MOFA": ("외교부 Open Data", SOURCE_LINKS["외교부 Open Data"]),
    "KOICA": ("KOICA", SOURCE_LINKS["KOICA"]),
    "KF": ("KF 데이터포털", SOURCE_LINKS["KF 데이터포털"]),
    "SAFETY": ("해외안전여행", SOURCE_LINKS["해외안전여행"]),
}


def initialize_database(database_path=DATABASE_PATH, reset=False):
    with get_connection(database_path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        if reset:
            _clear_seed_data(connection)

        country_count = connection.execute("SELECT COUNT(*) FROM countries").fetchone()[0]
        if country_count == 0:
            _seed_database(connection)

    return Path(database_path)


def _clear_seed_data(connection):
    for table in (
        "collection_logs",
        "risk_factors",
        "evidence",
        "recommendations",
        "projects",
        "signal_history",
        "country_indicators",
        "countries",
        "data_sources",
    ):
        connection.execute(f"DELETE FROM {table}")


def _seed_database(connection):
    _seed_sources(connection)

    with DATA_PATH.open(encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    for row in rows:
        iso3 = row["iso3"]
        connection.execute(
            """
            INSERT INTO countries (
                iso3, name, english_name, region, flag, completeness,
                risk_level, risk_score, reference_date, focus_fields,
                gap_opportunity, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                iso3,
                row["country"],
                row["english"],
                row["region"],
                row["flag"],
                int(row["completeness"]),
                row["risk_level"],
                int(row["risk_score"]),
                row["updated"],
                json.dumps(row["focus_fields"].split("·"), ensure_ascii=False),
                row["gap_opportunity"],
                row["summary"],
            ),
        )
        connection.executemany(
            "INSERT INTO country_indicators (country_iso3, code, value) VALUES (?, ?, ?)",
            [(iso3, code, int(row[code])) for code in INDICATOR_CODES],
        )
        connection.executemany(
            "INSERT INTO signal_history (country_iso3, year, score) VALUES (?, ?, ?)",
            [
                (iso3, year, score)
                for year, score in zip(range(2022, 2027), SIGNAL_HISTORY[iso3], strict=True)
            ],
        )
        _seed_country_analysis(connection, row)

    connection.executemany(
        """
        INSERT INTO collection_logs (
            source_code, collected_at, status, record_count, message
        ) VALUES (?, ?, 'seeded', ?, 'MVP 시범 데이터 초기 적재')
        """,
        [(source_code, "2026-07-13T00:00:00+09:00", len(rows)) for source_code in SOURCE_SEEDS],
    )


def _seed_sources(connection):
    connection.executemany(
        "INSERT INTO data_sources (code, name, url, description) VALUES (?, ?, ?, ?)",
        [
            (code, name, url, SOURCE_DESCRIPTIONS[name])
            for code, (name, url) in SOURCE_SEEDS.items()
        ],
    )


def _seed_country_analysis(connection, row):
    iso3 = row["iso3"]
    project = PROJECTS[iso3]
    connection.execute(
        """
        INSERT INTO projects (country_iso3, title, summary, partners, sdgs)
        VALUES (?, ?, ?, ?, ?)
        """,
        (iso3, project["title"], project["summary"], project["partners"], project["sdgs"]),
    )
    connection.executemany(
        "INSERT INTO recommendations (country_iso3, priority, title) VALUES (?, ?, ?)",
        [(iso3, priority, title) for priority, title in enumerate(project["models"], 1)],
    )
    connection.executemany(
        """
        INSERT INTO evidence (
            country_iso3, source_code, title, category, reference_date, is_demo
        ) VALUES (?, ?, ?, ?, ?, 1)
        """,
        [
            (iso3, source, title, category, row["updated"])
            for source, title, category in EVIDENCE[iso3]
        ],
    )
    connection.executemany(
        """
        INSERT INTO risk_factors (country_iso3, source_code, title, level, score)
        VALUES (?, 'SAFETY', ?, ?, ?)
        """,
        [
            (iso3, title, row["risk_level"], int(row["risk_score"]))
            for title in project["cautions"]
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="Initialize the SQLite demo database.")
    parser.add_argument("--reset", action="store_true", help="Delete and reload seed data.")
    parser.add_argument("--path", default=str(DATABASE_PATH), help="SQLite database path.")
    args = parser.parse_args()
    database_path = initialize_database(args.path, reset=args.reset)
    print(f"SQLite database ready: {database_path.resolve()}")


if __name__ == "__main__":
    main()
