# 0. 모듈 불러오기
from dataclasses import dataclass
from datetime import date

from backend.database.connection import get_connection
from backend.database.init_db import initialize_database
from config.settings import DATABASE_PATH


# 1. 분석 관련 조회 결과를 보관하는 레코드 모델
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


# 2. 추세, 프로젝트, 근거, 추천, 위험요인 조회 저장소
class AnalysisRepository:
    # 2.1. 데이터베이스 준비 및 경로 설정
    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = database_path
        initialize_database(self.database_path)

    # 2.2. 국가별 연도별 협력 신호 조회
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

    # 2.3. 국가별 대표 프로젝트와 해석 정보 조회
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

    # 2.4. 공공데이터 제공기관 목록 조회
    def list_sources(self):
        with get_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT code, name, url, description
                FROM data_sources ORDER BY code
                """
            ).fetchall()
        return [DataSourceRecord(**dict(row)) for row in rows]

    # 2.5. 국가별 분석 근거와 원문 URL 조회
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

    # 2.6. 국가별 추천 협력 모델 조회
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

    # 2.7. 국가별 주의 요인과 안전정보 출처 조회
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


# 3. API 전역에서 재사용하는 분석 저장소 인스턴스
analysis_repository = AnalysisRepository()
