"""초기 사업 검토안의 SQLite 캐시 저장소."""

import json

from backend.database.connection import get_connection
from backend.database.init_db import initialize_database
from backend.models.report import ReportRequest, ReportResponse
from config.settings import DATABASE_PATH


class ReportRepository:
    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = database_path
        initialize_database(self.database_path)

    def get(self, request_hash: str):
        with get_connection(self.database_path) as connection:
            row = connection.execute(
                "SELECT report_json FROM ai_reports WHERE request_hash = ?",
                (request_hash,),
            ).fetchone()
        return json.loads(row["report_json"]) if row else None

    def save(self, request: ReportRequest, response: ReportResponse):
        payload = json.dumps(response.model_dump(mode="json"), ensure_ascii=False)
        evidence_ids = json.dumps(
            [source.evidence_id for source in response.sources],
            ensure_ascii=False,
        )
        capabilities = json.dumps(request.capabilities, ensure_ascii=False)
        timestamp = response.generated_at.isoformat()
        with get_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO ai_reports (
                    request_hash, country_iso3, persona, field,
                    capabilities_json, prompt_version, generation_mode,
                    report_status, evidence_ids_json, report_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_hash) DO UPDATE SET
                    capabilities_json = excluded.capabilities_json,
                    prompt_version = excluded.prompt_version,
                    generation_mode = excluded.generation_mode,
                    report_status = excluded.report_status,
                    evidence_ids_json = excluded.evidence_ids_json,
                    report_json = excluded.report_json,
                    updated_at = excluded.updated_at
                """,
                (
                    response.request_hash,
                    request.country_iso3,
                    request.persona.value,
                    request.field.value,
                    capabilities,
                    response.prompt_version,
                    response.generation_mode,
                    response.status,
                    evidence_ids,
                    payload,
                    timestamp,
                    timestamp,
                ),
            )

    def count(self):
        with get_connection(self.database_path) as connection:
            return connection.execute("SELECT COUNT(*) FROM ai_reports").fetchone()[0]


report_repository = ReportRepository()
