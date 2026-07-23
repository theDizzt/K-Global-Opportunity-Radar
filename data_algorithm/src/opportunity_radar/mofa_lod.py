from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date

from .taxonomy_v2 import classify_sector
from .countries import TARGET_COUNTRIES, upsert_target_countries
from .ingest import _coverage, _source_record
from .public_api import IngestionRun, now_utc


LOD_DATASETS = {
    "mofapress": "http://opendata.mofa.go.kr/mofapress/sparql",
    "mofabrief": "http://opendata.mofa.go.kr/mofabrief/sparql",
    "mofapub": "http://opendata.mofa.go.kr/mofapub/sparql",
}


def _sparql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _first(values: dict[str, list[str]], tokens: tuple[str, ...]) -> str | None:
    for predicate, items in values.items():
        lowered = predicate.casefold()
        if any(token in lowered for token in tokens) and items:
            return items[0]
    return None


def _date_value(values: dict[str, list[str]]) -> str | None:
    raw = _first(values, ("date", "year", "created", "issued", "writ"))
    if not raw:
        return None
    match = re.search(r"(?:19|20)\d{2}(?:[-./]\d{1,2}(?:[-./]\d{1,2})?)?", raw)
    if not match:
        return None
    parts = match.group(0).replace(".", "-").replace("/", "-").split("-")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return f"{year:04d}-{month:02d}-{day:02d}"
    except ValueError:
        return None


class MofaLodCollector:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        transport: Callable[[str], bytes] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        max_retries: int = 4,
        datasets: dict[str, str] | None = None,
    ):
        self.conn = conn
        self.transport = transport or self._default_transport
        self.sleeper = sleeper
        self.max_retries = max_retries
        self.datasets = datasets or LOD_DATASETS

    @staticmethod
    def _default_transport(url: str) -> bytes:
        request = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "OpportunityRadar/0.1"}
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.read()

    def _query(self, run_id: int, dataset: str, endpoint: str, query: str, page: int) -> list[dict]:
        url = endpoint + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
        body: bytes | None = None
        for attempt in range(self.max_retries + 1):
            try:
                body = self.transport(url)
                break
            except urllib.error.HTTPError as exc:
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
        fingerprint = hashlib.sha256(query.encode("utf-8")).hexdigest()
        self.conn.execute(
            """INSERT OR REPLACE INTO raw_api_response(
                   run_id, source_type, endpoint, request_fingerprint, page_no,
                   fetched_at, http_status, body)
               VALUES (?, 'LOD', ?, ?, ?, ?, 200, ?)""",
            (run_id, endpoint, fingerprint, page, now_utc(), text),
        )
        payload = json.loads(text)
        return payload.get("results", {}).get("bindings", [])

    @staticmethod
    def _build_query(dataset: str, aliases: tuple[str, ...], page_size: int, offset: int) -> str:
        prefix = f"http://opendata.mofa.go.kr/{dataset}/resource/"
        alias_filter = " || ".join(
            f'CONTAINS(LCASE(STR(?matched)), LCASE("{_sparql_string(alias)}"))' for alias in aliases
        )
        return f"""
SELECT ?s ?p ?o WHERE {{
  {{ SELECT DISTINCT ?s WHERE {{
      ?s ?matchP ?matched .
      FILTER(STRSTARTS(STR(?s), "{prefix}"))
      FILTER(isLiteral(?matched) && ({alias_filter}))
    }} ORDER BY ?s LIMIT {int(page_size)} OFFSET {int(offset)} }}
  ?s ?p ?o .
  FILTER(isLiteral(?o))
}}
""".strip()

    def _store_rows(self, iso3: str, dataset: str, rows: list[dict]) -> int:
        grouped: dict[str, dict[str, list[str]]] = {}
        for row in rows:
            subject = row.get("s", {}).get("value")
            predicate = row.get("p", {}).get("value")
            value = row.get("o", {}).get("value")
            if not subject or not predicate or value is None:
                continue
            grouped.setdefault(subject, {}).setdefault(predicate, []).append(str(value))
        stored = 0
        for subject, properties in grouped.items():
            title = _first(properties, ("label", "title", "subject")) or subject.rsplit("/", 1)[-1]
            body_parts: list[str] = []
            for values in properties.values():
                for value in values:
                    if value not in body_parts:
                        body_parts.append(value)
            body = "\n".join(body_parts)
            sector, confidence = classify_sector(body)
            # One document can concern multiple countries; keep distinct evidence rows.
            identity = f"{iso3}|{subject}".encode("utf-8")
            external_id = f"LOD-{hashlib.sha1(identity).hexdigest()[:24]}"
            record_id = _source_record(
                self.conn, source="LOD", external_id=external_id, country=iso3,
                title=title, body=body[:20000], published_at=_date_value(properties),
                url=subject, raw={"dataset": dataset, "uri": subject, "properties": properties},
            )
            if sector:
                self.conn.execute(
                    """INSERT INTO evidence(source_record_id, country_iso3, sector_code,
                               event_type, event_date, organizations_json, confidence, supporting_text)
                       VALUES (?, ?, ?, 'press_mention', ?, '[]', ?, ?)
                       ON CONFLICT(source_record_id, sector_code, event_type) DO UPDATE SET
                         event_date=excluded.event_date, confidence=excluded.confidence,
                         supporting_text=excluded.supporting_text""",
                    (record_id, iso3, sector, _date_value(properties), min(0.9, confidence * 0.9), body[:4000]),
                )
            stored += 1
        return stored

    def collect(self, *, page_size: int = 100, max_pages: int | None = 10) -> dict[str, int]:
        upsert_target_countries(self.conn)
        run = IngestionRun(
            self.conn, "LOD",
            {"countries": list(TARGET_COUNTRIES), "datasets": list(self.datasets), "page_size": page_size},
        )
        counts = {iso3: 0 for iso3 in TARGET_COUNTRIES}
        try:
            for iso3, cfg in TARGET_COUNTRIES.items():
                aliases = tuple(cfg["aliases"])
                for dataset, endpoint in self.datasets.items():
                    page = 1
                    while True:
                        query = self._build_query(dataset, aliases, page_size, (page - 1) * page_size)
                        rows = self._query(run.id, dataset, endpoint, query, page)
                        subject_count = len({row.get("s", {}).get("value") for row in rows})
                        counts[iso3] += self._store_rows(iso3, dataset, rows)
                        self.conn.commit()
                        if subject_count < page_size or (max_pages is not None and page >= max_pages):
                            break
                        page += 1
                _coverage(self.conn, iso3, "LOD", counts[iso3], date.today().isoformat())
            run.complete(sum(counts.values()))
            return counts
        except Exception as exc:
            run.fail(exc)
            raise
