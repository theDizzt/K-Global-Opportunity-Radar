# 0. 모듈 불러오기
from dataclasses import dataclass

from backend.database.connection import get_connection
from backend.database.init_db import initialize_database
from config.settings import DATABASE_PATH


# 1. 동적 집계에 사용할 허용 열과 저장소 조회 결과 모델
GROUP_COLUMNS = {
    "dataset": "d.dataset_code",
    "field": "d.primary_field",
}


# 1.1. 최근 수집 로그와 누적 적재량 레코드
@dataclass(frozen=True)
class CollectionStatusRecord:
    collected_at: str | None
    status: str
    record_count: int
    message: str | None
    stored_documents: int
    covered_countries: int
    datasets: dict[str, int]


# 1.2. 국가별 문서 완전성과 분류 건수 레코드
@dataclass(frozen=True)
class QualityRecord:
    total_documents: int
    dated_documents: int
    summarized_documents: int
    shared_documents: int
    datasets: dict[str, int]
    fields: dict[str, int]


# 1.3. 근거 검토에 사용하는 정제 문서 레코드
@dataclass(frozen=True)
class DocumentRecord:
    title: str
    summary: str
    dataset_code: str
    primary_field: str
    published_date: str | None
    source_url: str


# 1.4. 연도·자료종류·분야별 문서 집계 레코드
@dataclass(frozen=True)
class SignalAggregateRecord:
    year: int
    dataset_code: str
    primary_field: str
    document_count: int


# 2. 수집 상태·품질·원시 신호 집계를 담당하는 저장소
class DataInsightRepository:
    # 2.1. 데이터베이스를 준비하고 조회 경로 설정
    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = database_path
        initialize_database(self.database_path)

    # 2.2. 기관의 최근 수집 로그와 현재 적재 현황 조회
    def get_collection_status(self, source_code: str):
        with get_connection(self.database_path) as connection:
            latest = connection.execute(
                """
                SELECT collected_at, status, record_count, message
                FROM collection_logs
                WHERE source_code = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (source_code,),
            ).fetchone()
            totals = connection.execute(
                """
                SELECT COUNT(DISTINCT d.document_uri) AS stored_documents,
                       COUNT(DISTINCT dc.country_iso3) AS covered_countries
                FROM source_documents AS d
                LEFT JOIN document_countries AS dc ON dc.document_uri = d.document_uri
                WHERE d.source_code = ?
                """,
                (source_code,),
            ).fetchone()
            datasets = connection.execute(
                """
                SELECT dataset_code, COUNT(*) AS document_count
                FROM source_documents
                WHERE source_code = ?
                GROUP BY dataset_code
                ORDER BY dataset_code
                """,
                (source_code,),
            ).fetchall()

        return CollectionStatusRecord(
            collected_at=latest["collected_at"] if latest else None,
            status=latest["status"] if latest else "not_collected",
            record_count=latest["record_count"] if latest else 0,
            message=latest["message"] if latest else None,
            stored_documents=totals["stored_documents"],
            covered_countries=totals["covered_countries"],
            datasets={row["dataset_code"]: row["document_count"] for row in datasets},
        )

    # 2.3. 국가별 날짜·요약문 누락과 다국가 중복 연결 현황 조회
    def get_quality(self, iso3: str):
        with get_connection(self.database_path) as connection:
            totals = connection.execute(
                """
                SELECT COUNT(*) AS total_documents,
                       SUM(CASE WHEN d.published_date IS NOT NULL THEN 1 ELSE 0 END) AS dated_documents,
                       SUM(CASE WHEN TRIM(d.summary) <> '' THEN 1 ELSE 0 END) AS summarized_documents,
                       SUM(CASE WHEN links.country_count > 1 THEN 1 ELSE 0 END) AS shared_documents
                FROM document_countries AS dc
                JOIN source_documents AS d ON d.document_uri = dc.document_uri
                JOIN (
                    SELECT document_uri, COUNT(*) AS country_count
                    FROM document_countries
                    GROUP BY document_uri
                ) AS links ON links.document_uri = d.document_uri
                WHERE dc.country_iso3 = ?
                """,
                (iso3,),
            ).fetchone()
            datasets = self._group_counts(connection, iso3, "dataset")
            fields = self._group_counts(connection, iso3, "field")

        return QualityRecord(
            total_documents=totals["total_documents"] or 0,
            dated_documents=totals["dated_documents"] or 0,
            summarized_documents=totals["summarized_documents"] or 0,
            shared_documents=totals["shared_documents"] or 0,
            datasets=datasets,
            fields=fields,
        )

    # 2.4. 품질 화면과 근거 검토에 사용할 최신 원문 목록 조회
    def list_documents(self, iso3: str, field: str | None, limit: int):
        with get_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT d.title, d.summary, d.dataset_code, d.primary_field,
                       d.published_date, d.source_url
                FROM source_documents AS d
                JOIN document_countries AS dc ON dc.document_uri = d.document_uri
                WHERE dc.country_iso3 = ?
                  AND (? IS NULL OR d.primary_field = ?)
                ORDER BY d.published_date IS NULL, d.published_date DESC, d.title
                LIMIT ?
                """,
                (iso3, field, field, limit),
            ).fetchall()
        return [DocumentRecord(**dict(row)) for row in rows]

    # 2.5. 국가·연도·자료종류·분야별 문서 건수 집계
    def get_signal_aggregates(self, iso3: str):
        with get_connection(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT CAST(SUBSTR(d.published_date, 1, 4) AS INTEGER) AS year,
                       d.dataset_code, d.primary_field, COUNT(*) AS document_count
                FROM source_documents AS d
                JOIN document_countries AS dc ON dc.document_uri = d.document_uri
                WHERE dc.country_iso3 = ?
                  AND d.published_date IS NOT NULL
                GROUP BY year, d.dataset_code, d.primary_field
                ORDER BY year, d.dataset_code, d.primary_field
                """,
                (iso3,),
            ).fetchall()
        return [SignalAggregateRecord(**dict(row)) for row in rows]

    # 2.6. 허용된 분류 열을 기준으로 문서 수 집계
    @staticmethod
    def _group_counts(connection, iso3: str, group_key: str):
        column = GROUP_COLUMNS[group_key]
        rows = connection.execute(
            f"""
            SELECT {column} AS group_name, COUNT(*) AS document_count
            FROM source_documents AS d
            JOIN document_countries AS dc ON dc.document_uri = d.document_uri
            WHERE dc.country_iso3 = ?
            GROUP BY {column}
            ORDER BY document_count DESC, group_name
            """,
            (iso3,),
        ).fetchall()
        return {row["group_name"]: row["document_count"] for row in rows}


# 3. API 전역에서 재사용하는 데이터 점검 저장소 인스턴스
data_insight_repository = DataInsightRepository()
