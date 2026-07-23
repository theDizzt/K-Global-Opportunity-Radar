# 0. 모듈 불러오기
from dataclasses import dataclass

from backend.database.connection import get_connection
from backend.database.init_db import initialize_database
from config.settings import DATABASE_PATH


# 1. 외부 데이터 수집 결과를 전달하는 레코드 모델
# 1.1. 외부 국가 식별자와 내부 ISO3 코드의 연결정보
@dataclass(frozen=True)
class CountryAlias:
    iso3: str
    source_uri: str
    source_code: str
    label: str


# 1.2. 정제된 원문과 관련 국가 정보를 전달하는 문서 레코드
@dataclass(frozen=True)
class SourceDocument:
    uri: str
    dataset_code: str
    title: str
    summary: str
    published_date: str | None
    source_url: str
    primary_field: str
    country_iso3: str


# 2. 외부 원본·정제 데이터와 수집 로그 저장소
class CollectionRepository:
    # 2.1. 데이터베이스 준비 및 경로 설정
    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = database_path
        initialize_database(self.database_path)

    # 2.2. SPARQL 원본 응답을 변경 없이 보관
    def save_raw_payload(
        self,
        source_code,
        dataset_code,
        requested_at,
        endpoint,
        query_text,
        status_code,
        payload_json,
    ):
        with get_connection(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO raw_source_payloads (
                    source_code, dataset_code, requested_at, endpoint,
                    query_text, status_code, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_code,
                    dataset_code,
                    requested_at,
                    endpoint,
                    query_text,
                    status_code,
                    payload_json,
                ),
            )
            return cursor.lastrowid

    # 2.3. 외교부 국가 URI와 내부 ISO3 코드 연결
    def upsert_country_aliases(self, source_code, aliases, updated_at):
        with get_connection(self.database_path) as connection:
            connection.executemany(
                """
                INSERT INTO country_aliases (
                    source_code, country_iso3, source_country_uri,
                    source_country_code, source_label, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_code, country_iso3) DO UPDATE SET
                    source_country_uri = excluded.source_country_uri,
                    source_country_code = excluded.source_country_code,
                    source_label = excluded.source_label,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        source_code,
                        alias.iso3,
                        alias.source_uri,
                        alias.source_code,
                        alias.label,
                        updated_at,
                    )
                    for alias in aliases
                ],
            )

    # 2.4. 정제 문서와 관련 국가를 중복 없이 저장
    def upsert_documents(self, source_code, documents, collected_at, raw_payload_id):
        with get_connection(self.database_path) as connection:
            for document in documents:
                connection.execute(
                    """
                    INSERT INTO source_documents (
                        document_uri, source_code, dataset_code, title, summary,
                        published_date, source_url, primary_field, collected_at,
                        raw_payload_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(document_uri) DO UPDATE SET
                        title = excluded.title,
                        summary = excluded.summary,
                        published_date = excluded.published_date,
                        source_url = excluded.source_url,
                        primary_field = excluded.primary_field,
                        collected_at = excluded.collected_at,
                        raw_payload_id = excluded.raw_payload_id
                    """,
                    (
                        document.uri,
                        source_code,
                        document.dataset_code,
                        document.title,
                        document.summary,
                        document.published_date,
                        document.source_url,
                        document.primary_field,
                        collected_at,
                        raw_payload_id,
                    ),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO document_countries (document_uri, country_iso3)
                    VALUES (?, ?)
                    """,
                    (document.uri, document.country_iso3),
                )

    # 2.5. 기관별 수집 성공·실패 상태와 적재 건수 기록
    def log_collection(self, source_code, collected_at, status, record_count, message):
        with get_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO collection_logs (
                    source_code, collected_at, status, record_count, message
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (source_code, collected_at, status, record_count, message),
            )
