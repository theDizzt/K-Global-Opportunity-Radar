# 0. 모듈 불러오기
from dataclasses import dataclass
from datetime import date

from backend.database.connection import get_connection
from backend.database.init_db import initialize_database
from config.settings import DATABASE_PATH


# 1. 분석 관련 조회 결과를 보관하는 레코드 모델
# 1.1. 근거 문서와 출처 정보를 전달하는 레코드
@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    title: str
    category: str
    source: str
    reference_date: date
    source_url: str
    is_demo: bool


# 1.2. 국가별 주의 요인과 출처를 전달하는 레코드
@dataclass(frozen=True)
class RiskRecord:
    title: str
    level: str
    score: int
    source: str
    source_url: str


# 1.3. 추천 프로젝트 설명을 전달하는 레코드
@dataclass(frozen=True)
class ProjectRecord:
    title: str
    summary: str
    partners: str
    sdgs: str


# 1.4. 공공데이터 제공기관 정보를 전달하는 레코드
@dataclass(frozen=True)
class DataSourceRecord:
    code: str
    name: str
    url: str
    description: str


@dataclass(frozen=True)
class OpportunityScoreRecord:
    country_iso3: str
    field: str
    score_version: str
    as_of_date: date
    demand_score: float
    policy_alignment_score: float
    readiness_score: float
    korean_base_score: float
    opportunity_score: float
    data_confidence: float
    is_demo: bool
    risk_level: int | None
    sensitivity_low: float | None
    sensitivity_high: float | None


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

    # 2.2.1. 데이터·알고리즘 파이프라인의 최신 국가·분야 점수 조회
    def get_opportunity_score(self, iso3: str, field: str):
        with get_connection(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM opportunity_scores
                WHERE country_iso3 = ? AND field = ?
                ORDER BY as_of_date DESC, score_version DESC
                LIMIT 1
                """,
                (iso3, field),
            ).fetchone()
        if row is None:
            return None
        values = dict(row)
        values["as_of_date"] = date.fromisoformat(values["as_of_date"])
        return OpportunityScoreRecord(**values)

    # 2.2.2. 실제 점수 스냅샷으로 연도별 추세 구성
    def get_opportunity_history(self, iso3: str, field: str):
        with get_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT substr(as_of_date, 1, 4) AS year,
                       AVG(opportunity_score) AS score
                FROM opportunity_scores
                WHERE country_iso3 = ? AND field = ?
                GROUP BY substr(as_of_date, 1, 4)
                ORDER BY year
                """,
                (iso3, field),
            ).fetchall()
        return [(int(row["year"]), round(row["score"])) for row in rows]

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

    # 2.5. 실제 수집 문서를 우선하고 없으면 시범 근거 조회
    def get_evidence(self, iso3: str, field: str | None = None):
        live_evidence = self._get_live_evidence(iso3, field)
        if live_evidence:
            return live_evidence

        with get_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT e.id, e.title, e.category, e.reference_date, e.is_demo,
                       s.name AS source, s.url AS source_url
                FROM evidence AS e
                JOIN data_sources AS s ON s.code = e.source_code
                WHERE e.country_iso3 = ? ORDER BY e.id
                """,
                (iso3,),
            ).fetchall()
        return [
            EvidenceRecord(
                evidence_id=f"seed:{row['id']}",
                title=row["title"],
                category=row["category"],
                source=row["source"],
                reference_date=date.fromisoformat(row["reference_date"]),
                source_url=row["source_url"],
                is_demo=bool(row["is_demo"]),
            )
            for row in rows
        ]

    # 2.5.1. 선택 분야와 일치하는 외교부 LOD 문서를 최신순으로 조회
    def _get_live_evidence(self, iso3: str, field: str | None):
        with get_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT d.document_uri, d.title, d.primary_field, d.published_date,
                       d.source_url, d.dataset_code, s.name AS source
                FROM source_documents AS d
                JOIN document_countries AS dc ON dc.document_uri = d.document_uri
                JOIN data_sources AS s ON s.code = d.source_code
                WHERE dc.country_iso3 = ?
                  AND d.published_date IS NOT NULL
                  AND (? IS NULL OR d.primary_field IN (?, '외교 일반'))
                ORDER BY
                    CASE WHEN d.primary_field = ? THEN 0 ELSE 1 END,
                    d.published_date DESC,
                    d.title
                LIMIT 3
                """,
                (iso3, field, field, field),
            ).fetchall()
        dataset_names = {
            "mofadaily": "외교일지",
            "mofapress": "보도자료",
        }
        return [
            EvidenceRecord(
                evidence_id=row["document_uri"],
                title=row["title"],
                category=f"{dataset_names.get(row['dataset_code'], '외교자료')} · {row['primary_field']}",
                source=row["source"],
                reference_date=date.fromisoformat(row["published_date"]),
                source_url=row["source_url"],
                is_demo=False,
            )
            for row in rows
        ]

    # 2.5.2. 국가별로 적재된 실제 외교부 문서 수 조회
    def count_live_documents(self, iso3: str):
        with get_connection(self.database_path) as connection:
            return connection.execute(
                """
                SELECT COUNT(*)
                FROM document_countries AS dc
                JOIN source_documents AS d ON d.document_uri = dc.document_uri
                WHERE dc.country_iso3 = ?
                """,
                (iso3,),
            ).fetchone()[0]

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
