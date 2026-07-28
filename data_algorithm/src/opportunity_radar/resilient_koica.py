from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date

from .koica_pipeline import KOICA_SCHEMA, PROJECT_TYPES, TARGET_COUNTRIES, KoicaCollector, _country_iso3, _now


class ResilientKoicaCollector(KoicaCollector):
    """KOICA collector that isolates failed year/type slices instead of aborting all data."""

    def collect(
        self,
        *,
        years: Iterable[int] = range(1991, date.today().year + 1),
        project_types: Iterable[str] = PROJECT_TYPES,
        page_size: int = 100,
        fetch_details: bool = True,
    ) -> dict[str, int]:
        years = tuple(years)
        project_types = tuple(project_types)
        self._upsert_countries()
        self.conn.executescript(KOICA_SCHEMA)
        cursor = self.conn.execute(
            "INSERT INTO ingestion_run(source_type, started_at, status, parameters_json) "
            "VALUES ('KOICA', ?, 'running', ?)",
            (
                _now(),
                json.dumps({
                    "years": years,
                    "project_types": project_types,
                    "page_size": page_size,
                    "fetch_details": fetch_details,
                }),
            ),
        )
        run_id = cursor.lastrowid
        self.conn.commit()
        counts = {iso3: 0 for iso3 in TARGET_COUNTRIES}
        seen: set[str] = set()
        errors: list[dict[str, object]] = []

        for year in years:
            for project_type in project_types:
                try:
                    for item in self._list_items(run_id, year, project_type, page_size):
                        iso3 = _country_iso3(
                            item.get("NATION_NM", ""),
                            item.get("NATION_CD"),
                        )
                        project_no = item.get("BSNS_NO", "")
                        if not iso3 or not project_no or project_no in seen:
                            continue
                        if fetch_details:
                            try:
                                detail, statuses = self._detail(run_id, project_no)
                            except Exception as exc:
                                self._record_failure(
                                    run_id, year, project_type, exc, project_no=project_no
                                )
                                errors.append({
                                    "year": year, "project_type": project_type,
                                    "project_no": project_no, "error": str(exc)[:300],
                                })
                                # The provider's detail endpoint can return
                                # RESULT_CODE 99 even when the corresponding list
                                # endpoint succeeds. Preserve the list-level project.
                                detail = {"DETAIL_FETCH_ERROR": str(exc)[:300]}
                                statuses = []
                        else:
                            detail = {"DETAIL_FETCH_SKIPPED": "list_only_mode"}
                            statuses = []
                        stored_country = self._upsert_project(item, detail, statuses)
                        seen.add(project_no)
                        counts[stored_country] += 1
                        self.conn.commit()
                except Exception as exc:
                    self._record_failure(run_id, year, project_type, exc)
                    errors.append({
                        "year": year, "project_type": project_type, "error": str(exc)[:300],
                    })

        observed_at = date.today().isoformat()
        for iso3, count in counts.items():
            self.conn.execute(
                """INSERT INTO source_coverage(country_iso3, source_type, observed_at, record_count)
                   VALUES (?, 'KOICA', ?, ?)
                   ON CONFLICT(country_iso3, source_type) DO UPDATE SET
                     observed_at=excluded.observed_at, record_count=excluded.record_count""",
                (iso3, observed_at, count),
            )
        status = "partial" if errors else "complete"
        self.conn.execute(
            """UPDATE ingestion_run SET finished_at=?, status=?, record_count=?, error_message=?
               WHERE id=?""",
            (_now(), status, sum(counts.values()), json.dumps(errors, ensure_ascii=False)[:1000] or None, run_id),
        )
        self.conn.commit()
        return counts

    def _record_failure(
        self, run_id: int, year: int, project_type: str,
        exc: Exception, *, project_no: str | None = None,
    ) -> None:
        payload = {
            "run_id": run_id, "year": year, "project_type": project_type,
            "project_no": project_no, "error": str(exc)[:300],
        }
        self.conn.execute(
            """INSERT INTO data_quality_issue(source_type, external_id, issue_type,
                       field_name, raw_value, detected_at)
               VALUES ('KOICA', ?, 'api_slice_failed', 'year_project_type', ?, ?)""",
            (project_no, json.dumps(payload, ensure_ascii=False), date.today().isoformat()),
        )
        self.conn.commit()
