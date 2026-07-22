from dataclasses import dataclass
from datetime import date

from backend.database.connection import get_connection
from backend.database.init_db import initialize_database
from config.settings import DATABASE_PATH


@dataclass(frozen=True)
class EvidenceRecord:
    title: str
    category: str
    source: str
    reference_date: date
    source_url: str
    is_demo: bool


@dataclass(frozen=True)
class RiskRecord:
    title: str
    level: str
    score: int
    source: str
    source_url: str


@dataclass(frozen=True)
class ProjectRecord:
    title: str
    summary: str
    partners: str
    sdgs: str


@dataclass(frozen=True)
class DataSourceRecord:
    code: str
    name: str
    url: str
    description: str


class AnalysisRepository:
    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = database_path
        initialize_database(self.database_path)

    def get_signal_history(self, iso3: str):
        with get_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT year, score FROM signal_history
                WHERE country_iso3 = ? ORDER BY year
                """,
                (iso3,),
            ).fetchall()
        return [(row["year"], row["score"]) for row in rows]

    def get_project(self, iso3: str):
        with get_connection(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT title, summary, partners, sdgs
                FROM projects WHERE country_iso3 = ?
                """,
                (iso3,),
            ).fetchone()
        if row is None:
            raise LookupError(f"Project data not found for country: {iso3}")
        return ProjectRecord(**dict(row))

    def list_sources(self):
        with get_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT code, name, url, description
                FROM data_sources ORDER BY code
                """
            ).fetchall()
        return [DataSourceRecord(**dict(row)) for row in rows]

    def get_evidence(self, iso3: str):
        with get_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT e.title, e.category, e.reference_date, e.is_demo,
                       s.name AS source, s.url AS source_url
                FROM evidence AS e
                JOIN data_sources AS s ON s.code = e.source_code
                WHERE e.country_iso3 = ? ORDER BY e.id
                """,
                (iso3,),
            ).fetchall()
        return [
            EvidenceRecord(
                title=row["title"],
                category=row["category"],
                source=row["source"],
                reference_date=date.fromisoformat(row["reference_date"]),
                source_url=row["source_url"],
                is_demo=bool(row["is_demo"]),
            )
            for row in rows
        ]

    def get_recommendations(self, iso3: str):
        with get_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT title FROM recommendations
                WHERE country_iso3 = ? ORDER BY priority
                """,
                (iso3,),
            ).fetchall()
        return [row["title"] for row in rows]

    def get_risks(self, iso3: str):
        with get_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT r.title, r.level, r.score,
                       s.name AS source, s.url AS source_url
                FROM risk_factors AS r
                JOIN data_sources AS s ON s.code = r.source_code
                WHERE r.country_iso3 = ? ORDER BY r.id
                """,
                (iso3,),
            ).fetchall()
        return [
            RiskRecord(
                title=row["title"],
                level=row["level"],
                score=row["score"],
                source=row["source"],
                source_url=row["source_url"],
            )
            for row in rows
        ]


analysis_repository = AnalysisRepository()
