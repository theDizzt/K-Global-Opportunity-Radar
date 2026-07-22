import json
from dataclasses import dataclass
from datetime import date

from backend.database.connection import get_connection
from backend.database.init_db import initialize_database
from backend.models.country import CountryDetail, CountrySummary, IndicatorValues
from config.settings import DATABASE_PATH


@dataclass(frozen=True)
class CountryRecord:
    iso3: str
    country: str
    english: str
    region: str
    flag: str
    diplomacy: int
    oda: int
    korean_base: int
    people_exchange: int
    esg: int
    completeness: int
    risk_level: str
    risk_score: int
    updated: date
    focus_fields: tuple[str, ...]
    gap_opportunity: str
    summary: str

    def to_summary(self):
        return CountrySummary(
            iso3=self.iso3,
            name=self.country,
            english_name=self.english,
            region=self.region,
            flag=self.flag,
            data_completeness=self.completeness,
            reference_date=self.updated,
        )

    def to_detail(self):
        return CountryDetail(
            **self.to_summary().model_dump(),
            indicators=IndicatorValues(
                diplomacy=self.diplomacy,
                oda=self.oda,
                korean_base=self.korean_base,
                people_exchange=self.people_exchange,
                esg=self.esg,
            ),
            risk_level=self.risk_level,
            risk_score=self.risk_score,
            focus_fields=list(self.focus_fields),
            gap_opportunity=self.gap_opportunity,
            summary=self.summary,
        )


class CountryRepository:
    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = database_path
        initialize_database(self.database_path)

    def list_all(self, region: str | None = None):
        query = _COUNTRY_QUERY
        parameters = ()
        if region is not None:
            query += " WHERE c.region = ?"
            parameters = (region,)
        query += " GROUP BY c.iso3 ORDER BY c.name"

        with get_connection(self.database_path) as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._to_record(row) for row in rows]

    def get_by_iso3(self, iso3: str):
        query = _COUNTRY_QUERY + " WHERE c.iso3 = ? GROUP BY c.iso3"
        with get_connection(self.database_path) as connection:
            row = connection.execute(query, (iso3.strip().upper(),)).fetchone()
        return self._to_record(row) if row else None

    def count(self):
        with get_connection(self.database_path) as connection:
            return connection.execute("SELECT COUNT(*) FROM countries").fetchone()[0]

    @staticmethod
    def _to_record(row):
        return CountryRecord(
            iso3=row["iso3"],
            country=row["name"],
            english=row["english_name"],
            region=row["region"],
            flag=row["flag"],
            diplomacy=row["diplomacy"],
            oda=row["oda"],
            korean_base=row["korean_base"],
            people_exchange=row["people_exchange"],
            esg=row["esg"],
            completeness=row["completeness"],
            risk_level=row["risk_level"],
            risk_score=row["risk_score"],
            updated=date.fromisoformat(row["reference_date"]),
            focus_fields=tuple(json.loads(row["focus_fields"])),
            gap_opportunity=row["gap_opportunity"],
            summary=row["summary"],
        )


_COUNTRY_QUERY = """
    SELECT
        c.*,
        MAX(CASE WHEN i.code = 'diplomacy' THEN i.value END) AS diplomacy,
        MAX(CASE WHEN i.code = 'oda' THEN i.value END) AS oda,
        MAX(CASE WHEN i.code = 'korean_base' THEN i.value END) AS korean_base,
        MAX(CASE WHEN i.code = 'people_exchange' THEN i.value END) AS people_exchange,
        MAX(CASE WHEN i.code = 'esg' THEN i.value END) AS esg
    FROM countries AS c
    JOIN country_indicators AS i ON i.country_iso3 = c.iso3
"""


country_repository = CountryRepository()
