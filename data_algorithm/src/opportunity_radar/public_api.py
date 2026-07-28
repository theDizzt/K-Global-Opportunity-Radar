from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from datetime import datetime, timezone


# 1. 수집 실행 이력과 원본 API 응답을 보존하는 공통 스키마
INGESTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestion_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS raw_api_response (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES ingestion_run(id),
    source_type TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    page_no INTEGER,
    fetched_at TEXT NOT NULL,
    http_status INTEGER NOT NULL,
    body TEXT NOT NULL,
    UNIQUE(run_id, request_fingerprint)
);
"""


# 2. 모든 수집 시각을 UTC ISO 형식으로 통일
def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# 3. 수집 이력 테이블이 없는 데이터베이스를 안전하게 초기화
def ensure_ingestion_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(INGESTION_SCHEMA)
    conn.commit()


# 4. 공공데이터포털 응답 오류를 호출 코드와 구분하기 위한 예외
class PublicApiError(RuntimeError):
    pass


# 5. 인증·재시도·페이지네이션·원문 보존을 담당하는 공통 API 클라이언트
class DataGoKrClient:
    """Small JSON client that preserves every successful source response."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        service_key: str,
        *,
        transport: Callable[[str], bytes] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        max_retries: int = 4,
    ):
        self.conn = conn
        self.service_key = urllib.parse.unquote(service_key.strip())
        if not self.service_key:
            raise ValueError("Public data portal service key is empty")
        self.transport = transport or self._default_transport
        self.sleeper = sleeper
        self.max_retries = max_retries
        ensure_ingestion_schema(conn)

    @staticmethod
    def _default_transport(url: str) -> bytes:
        # 공식 API가 호출 주체를 식별할 수 있도록 서비스 User-Agent를 전달합니다.
        request = urllib.request.Request(url, headers={"User-Agent": "OpportunityRadar/0.1"})
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()

    def call(
        self,
        run_id: int,
        source_type: str,
        endpoint: str,
        params: dict[str, object],
        *,
        page_no: int | None = None,
    ) -> dict:
        # 빈 값은 요청에서 제외하고 인증키를 디코딩한 상태로 한 번만 인코딩합니다.
        safe_params = {key: str(value) for key, value in params.items() if value is not None}
        query = urllib.parse.urlencode({"serviceKey": self.service_key, "returnType": "JSON", **safe_params})
        url = f"{endpoint}?{query}"
        body: bytes | None = None
        for attempt in range(self.max_retries + 1):
            try:
                body = self.transport(url)
                break
            except urllib.error.HTTPError as exc:
                if exc.code in {401, 403}:
                    raise PublicApiError(
                        f"{source_type} API authorization failed (HTTP {exc.code}); "
                        "verify that this API is approved for the service key."
                    ) from exc
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= self.max_retries:
                    raise
                exc.close()
                self.sleeper(min(2**attempt, 8))
            except (urllib.error.URLError, TimeoutError):
                if attempt >= self.max_retries:
                    raise
                self.sleeper(min(2**attempt, 8))
        assert body is not None
        text = body.decode("utf-8", "replace")
        # 같은 실행에서 동일 요청이 중복 저장되지 않도록 URL 매개변수를 해시합니다.
        fingerprint = hashlib.sha256(
            json.dumps({"endpoint": endpoint, "params": safe_params}, sort_keys=True).encode()
        ).hexdigest()
        self.conn.execute(
            """INSERT OR REPLACE INTO raw_api_response(
                   run_id, source_type, endpoint, request_fingerprint, page_no,
                   fetched_at, http_status, body
               ) VALUES (?, ?, ?, ?, ?, ?, 200, ?)""",
            (run_id, source_type, endpoint, fingerprint, page_no, now_utc(), text),
        )
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PublicApiError(f"{source_type} returned a non-JSON response") from exc
        header = payload.get("response", {}).get("header", {})
        code = str(header.get("resultCode", "0"))
        if code not in {"0", "00", "0000", "INFO-0"}:
            raise PublicApiError(f"{source_type} API error {code}: {header.get('resultMsg', 'unknown error')}")
        return payload

    def pages(
        self,
        run_id: int,
        source_type: str,
        endpoint: str,
        params: dict[str, object],
        *,
        page_size: int = 100,
        max_pages: int | None = None,
    ) -> Iterator[dict]:
        # 전체 건수와 현재 페이지 크기를 함께 확인해 마지막 페이지를 판별합니다.
        page = 1
        while True:
            payload = self.call(
                run_id,
                source_type,
                endpoint,
                {**params, "numOfRows": page_size, "pageNo": page},
                page_no=page,
            )
            body = payload.get("response", {}).get("body", {})
            items = body.get("items", {}).get("item", []) if isinstance(body, dict) else []
            if isinstance(items, dict):
                items = [items]
            for item in items or []:
                yield item
            total = int(body.get("totalCount") or 0)
            if not items or page * page_size >= total or len(items) < page_size:
                break
            if max_pages is not None and page >= max_pages:
                break
            page += 1


# 6. 수집 성공·실패·건수를 하나의 실행 단위로 기록
class IngestionRun:
    def __init__(self, conn: sqlite3.Connection, source_type: str, parameters: dict):
        self.conn = conn
        self.source_type = source_type
        ensure_ingestion_schema(conn)
        cur = conn.execute(
            "INSERT INTO ingestion_run(source_type, started_at, status, parameters_json) VALUES (?, ?, 'running', ?)",
            (source_type, now_utc(), json.dumps(parameters, ensure_ascii=False)),
        )
        self.id = int(cur.lastrowid)

    def complete(self, count: int) -> None:
        self.conn.execute(
            "UPDATE ingestion_run SET finished_at=?, status='complete', record_count=? WHERE id=?",
            (now_utc(), count, self.id),
        )
        self.conn.commit()

    def fail(self, exc: Exception) -> None:
        self.conn.execute(
            "UPDATE ingestion_run SET finished_at=?, status='failed', error_message=? WHERE id=?",
            (now_utc(), str(exc)[:1000], self.id),
        )
        self.conn.commit()
