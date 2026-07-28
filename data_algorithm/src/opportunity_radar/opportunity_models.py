from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Iterable

from .donor_supply import (
    all_donor_supply_metrics,
    donor_supply_momentum_metrics,
    ensure_donor_supply_schema,
)
from .policy_evidence import classify_policy_evidence
from .project_history import ensure_project_history_schema
from .statistical_signals import (
    ensure_signal_schema,
    predict_current_candidates,
    sync_signal_events,
)
from .taxonomy_v2 import SECTORS


MODEL_VERSION = "v1.4-policy-implementation-screen"
PROFILE_VERSION = "v1.4-no-forced-composite"
WORLD_BANK_API = "https://api.worldbank.org/v2"
HIGH_NEED_THRESHOLD = 60.0
MAX_INDICATOR_AGE_YEARS = 7


MODEL_SCHEMA = """
CREATE TABLE IF NOT EXISTS development_indicator_observation (
    source_type TEXT NOT NULL,
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    indicator_code TEXT NOT NULL,
    indicator_name TEXT NOT NULL,
    observation_year INTEGER NOT NULL,
    value REAL NOT NULL,
    fetched_at TEXT NOT NULL,
    source_url TEXT NOT NULL,
    raw_json TEXT,
    PRIMARY KEY(source_type, country_iso3, indicator_code, observation_year)
);

CREATE TABLE IF NOT EXISTS opportunity_model_score (
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    sector_code TEXT NOT NULL REFERENCES sector(code),
    snapshot_year INTEGER NOT NULL,
    model_code TEXT NOT NULL,
    model_version TEXT NOT NULL,
    score REAL,
    evidence_status TEXT NOT NULL,
    data_coverage REAL NOT NULL,
    components_json TEXT NOT NULL,
    caveats_json TEXT NOT NULL,
    source_urls_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(
        country_iso3, sector_code, snapshot_year, model_code, model_version
    )
);

CREATE TABLE IF NOT EXISTS opportunity_candidate_profile (
    country_iso3 TEXT NOT NULL REFERENCES country(iso3),
    sector_code TEXT NOT NULL REFERENCES sector(code),
    snapshot_year INTEGER NOT NULL,
    profile_version TEXT NOT NULL,
    continuity_score REAL,
    unmet_need_score REAL,
    korean_supply_intensity REAL,
    all_donor_saturation REAL,
    all_donor_momentum REAL,
    korea_supply_share REAL,
    readiness_score REAL,
    implementation_feasibility_score REAL,
    implementation_status TEXT,
    policy_fit_score REAL,
    decision_status TEXT NOT NULL,
    candidate_type TEXT NOT NULL,
    rationale_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(country_iso3, sector_code, snapshot_year, profile_version)
);

CREATE INDEX IF NOT EXISTS idx_model_score_lookup
ON opportunity_model_score(model_code, snapshot_year, score DESC);
CREATE INDEX IF NOT EXISTS idx_candidate_profile_type
ON opportunity_candidate_profile(snapshot_year, candidate_type);
"""


@dataclass(frozen=True)
class NeedIndicator:
    sector_code: str
    indicator_code: str
    indicator_name: str
    need_direction: str
    weight: float = 1.0


NEED_INDICATORS: tuple[NeedIndicator, ...] = (
    NeedIndicator(
        "education",
        "SE.SEC.ENRR",
        "School enrollment, secondary (% gross)",
        "lower_value_more_need",
    ),
    NeedIndicator(
        "education",
        "SE.SEC.CMPT.LO.ZS",
        "Lower secondary completion rate (% of relevant age group)",
        "lower_value_more_need",
    ),
    NeedIndicator(
        "education",
        "SE.PRM.CMPT.ZS",
        "Primary completion rate (% of relevant age group)",
        "lower_value_more_need",
    ),
    NeedIndicator(
        "digital",
        "IT.NET.USER.ZS",
        "Individuals using the Internet (% of population)",
        "lower_value_more_need",
    ),
    NeedIndicator(
        "digital",
        "IT.NET.BBND.P2",
        "Fixed broadband subscriptions (per 100 people)",
        "lower_value_more_need",
    ),
    NeedIndicator(
        "digital",
        "IT.CEL.SETS.P2",
        "Mobile cellular subscriptions (per 100 people)",
        "lower_value_more_need",
    ),
    NeedIndicator(
        "health",
        "SH_UHC_SCI",
        "UHC service coverage index",
        "lower_value_more_need",
    ),
    NeedIndicator(
        "health",
        "SH.DYN.MORT",
        "Mortality rate, under-5 (per 1,000 live births)",
        "higher_value_more_need",
    ),
    NeedIndicator(
        "health",
        "SH.STA.MMRT",
        "Maternal mortality ratio (per 100,000 live births)",
        "higher_value_more_need",
    ),
)


def ensure_opportunity_model_schema(conn: sqlite3.Connection) -> None:
    ensure_project_history_schema(conn)
    ensure_signal_schema(conn)
    ensure_donor_supply_schema(conn)
    conn.executescript(MODEL_SCHEMA)
    profile_columns = {
        row[1] for row in conn.execute(
            "PRAGMA table_info(opportunity_candidate_profile)"
        )
    }
    if "all_donor_saturation" not in profile_columns:
        conn.execute(
            "ALTER TABLE opportunity_candidate_profile "
            "ADD COLUMN all_donor_saturation REAL"
        )
    if "korea_supply_share" not in profile_columns:
        conn.execute(
            "ALTER TABLE opportunity_candidate_profile "
            "ADD COLUMN korea_supply_share REAL"
        )
    if "all_donor_momentum" not in profile_columns:
        conn.execute(
            "ALTER TABLE opportunity_candidate_profile "
            "ADD COLUMN all_donor_momentum REAL"
        )
    if "implementation_feasibility_score" not in profile_columns:
        conn.execute(
            "ALTER TABLE opportunity_candidate_profile "
            "ADD COLUMN implementation_feasibility_score REAL"
        )
    if "implementation_status" not in profile_columns:
        conn.execute(
            "ALTER TABLE opportunity_candidate_profile "
            "ADD COLUMN implementation_status TEXT"
        )
    conn.commit()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _world_bank_url(
    countries: Iterable[str] | str,
    indicator_code: str,
    *,
    start_year: int,
    end_year: int,
    latest_only: bool = False,
) -> str:
    country_path = (
        countries
        if isinstance(countries, str)
        else ";".join(country.upper() for country in countries)
    )
    parameters: dict[str, object] = {
        "format": "json",
        "per_page": 20000,
    }
    if latest_only:
        parameters["mrnev"] = 1
    else:
        parameters["date"] = f"{start_year}:{end_year}"
    query = urllib.parse.urlencode(parameters)
    return (
        f"{WORLD_BANK_API}/country/{country_path}/indicator/"
        f"{urllib.parse.quote(indicator_code)}?{query}"
    )


def collect_world_bank_need_indicators(
    conn: sqlite3.Connection,
    *,
    countries: Iterable[str],
    start_year: int = 2015,
    end_year: int | None = None,
    request_interval_seconds: float = 1.0,
    timeout_seconds: float = 30.0,
    country_batch_size: int = 40,
    validate_world_bank_countries: bool = True,
    max_attempts_per_batch: int = 2,
    use_all_countries_endpoint: bool = False,
    latest_only: bool = True,
    opener: Callable[..., object] = urllib.request.urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Collect the pilot need indicators using one batched call per indicator.

    The World Bank Indicators API does not require an API key. Countries are
    batched per indicator to reduce load, and a conservative delay is retained
    between calls.
    """
    ensure_opportunity_model_schema(conn)
    selected = tuple(dict.fromkeys(country.upper() for country in countries))
    if not selected:
        raise ValueError("At least one country is required")
    if country_batch_size < 1:
        raise ValueError("country_batch_size must be at least 1")
    if max_attempts_per_batch < 1:
        raise ValueError("max_attempts_per_batch must be at least 1")
    known = {
        row[0]
        for row in conn.execute(
            f"SELECT iso3 FROM country WHERE iso3 IN ({','.join('?' for _ in selected)})",
            selected,
        )
    }
    unknown = sorted(set(selected) - known)
    if unknown:
        raise ValueError(f"Unknown country ISO3 codes: {', '.join(unknown)}")

    last_year = end_year or date.today().year
    fetched_at = _utc_now()
    inserted = 0
    requests = 0
    errors: list[dict[str, str]] = []
    urls: list[str] = []
    attempted = 0
    request_countries = selected
    unsupported_countries: list[str] = []
    if validate_world_bank_countries and not use_all_countries_endpoint:
        country_url = f"{WORLD_BANK_API}/country?format=json&per_page=400"
        urls.append(country_url)
        country_request = urllib.request.Request(
            country_url,
            headers={
                "User-Agent": "K-Global-Opportunity-Radar/0.1 (+public-data-research)",
                "Accept": "application/json",
            },
        )
        attempted += 1
        try:
            response = opener(country_request, timeout=timeout_seconds)
            with response:
                country_payload = json.loads(
                    response.read().decode("utf-8-sig")
                )
            if not isinstance(country_payload, list) or len(country_payload) < 2:
                raise ValueError("Unexpected World Bank country response shape")
            supported = {
                str(item.get("id") or "").upper()
                for item in (country_payload[1] or [])
                if re.fullmatch(r"[A-Z]{3}", str(item.get("id") or "").upper())
                and str((item.get("region") or {}).get("value") or "")
                != "Aggregates"
            }
            request_countries = tuple(
                country for country in selected if country in supported
            )
            unsupported_countries = sorted(set(selected) - set(request_countries))
            requests += 1
        except Exception as exc:
            errors.append(
                {
                    "indicator_code": "WORLD_BANK_COUNTRY_LIST",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    batches: list[tuple[str, ...] | str]
    if use_all_countries_endpoint:
        batches = ["all"]
    else:
        batches = [
            request_countries[index : index + country_batch_size]
            for index in range(0, len(request_countries), country_batch_size)
        ]
    for spec in NEED_INDICATORS:
        for batch in batches:
            url = _world_bank_url(
                batch,
                spec.indicator_code,
                start_year=start_year,
                end_year=last_year,
                latest_only=latest_only,
            )
            urls.append(url)
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "K-Global-Opportunity-Radar/0.1 (+public-data-research)",
                    "Accept": "application/json",
                },
            )
            last_error: Exception | None = None
            for _attempt in range(max_attempts_per_batch):
                if attempted and request_interval_seconds > 0:
                    sleeper(request_interval_seconds)
                attempted += 1
                try:
                    response = opener(request, timeout=timeout_seconds)
                    with response:
                        payload = json.loads(
                            response.read().decode("utf-8-sig")
                        )
                    if not isinstance(payload, list) or len(payload) < 2:
                        raise ValueError("Unexpected World Bank response shape")
                    observations = payload[1] or []
                    for item in observations:
                        value = item.get("value")
                        country = str(
                            item.get("countryiso3code") or ""
                        ).upper()
                        year_text = str(item.get("date") or "")
                        if (
                            value is None
                            or country not in known
                            or not year_text.isdigit()
                        ):
                            continue
                        conn.execute(
                            """INSERT INTO development_indicator_observation(
                                   source_type, country_iso3, indicator_code,
                                   indicator_name, observation_year, value,
                                   fetched_at, source_url, raw_json
                               ) VALUES (
                                   'WORLD_BANK_WDI', ?, ?, ?, ?, ?, ?, ?, ?
                               )
                               ON CONFLICT(
                                   source_type, country_iso3, indicator_code,
                                   observation_year
                               ) DO UPDATE SET
                                 indicator_name=excluded.indicator_name,
                                 value=excluded.value,
                                 fetched_at=excluded.fetched_at,
                                 source_url=excluded.source_url,
                                 raw_json=excluded.raw_json""",
                            (
                                country,
                                spec.indicator_code,
                                spec.indicator_name,
                                int(year_text),
                                float(value),
                                fetched_at,
                                url,
                                _json(item),
                            ),
                        )
                        inserted += 1
                    conn.commit()
                    requests += 1
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
            if last_error is not None:  # preserve successful indicator batches
                errors.append(
                    {
                        "indicator_code": spec.indicator_code,
                        "countries": (
                            batch if isinstance(batch, str) else ",".join(batch)
                        ),
                        "error": f"{type(last_error).__name__}: {last_error}",
                    }
                )
    conn.commit()
    return {
        "countries": list(selected),
        "requested_countries": list(request_countries),
        "unsupported_countries": unsupported_countries,
        "requests": requests,
        "attempted_requests": attempted,
        "country_batch_size": country_batch_size,
        "used_all_countries_endpoint": use_all_countries_endpoint,
        "latest_only": latest_only,
        "observations_upserted": inserted,
        "errors": errors,
        "source_urls": urls,
    }


def _world_bank_bulk_url(indicator_code: str) -> str:
    query = urllib.parse.urlencode(
        {
            "source": 2,
            "downloadformat": "csv",
            "dataformat": "table",
        }
    )
    return (
        f"{WORLD_BANK_API}/country/all/indicator/"
        f"{urllib.parse.quote(indicator_code)}?{query}"
    )


def _world_bank_data_csv_member(archive: zipfile.ZipFile) -> str:
    candidates = [
        name
        for name in archive.namelist()
        if name.lower().endswith(".csv")
        and name.rsplit("/", 1)[-1].startswith("API_")
    ]
    if not candidates:
        raise ValueError("World Bank ZIP does not contain an API data CSV")
    return sorted(candidates)[0]


def collect_world_bank_bulk_need_indicators(
    conn: sqlite3.Connection,
    *,
    countries: Iterable[str],
    start_year: int = 2015,
    end_year: int | None = None,
    request_interval_seconds: float = 1.0,
    timeout_seconds: float = 120.0,
    max_attempts_per_indicator: int = 2,
    opener: Callable[..., object] = urllib.request.urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Collect all comparison countries from one zipped CSV per indicator.

    The World Bank download endpoint is substantially more reliable than a
    long semicolon-delimited JSON country query. Only requested countries and
    years are retained, while each successful indicator is committed
    independently so a later failure does not discard earlier downloads.
    """
    ensure_opportunity_model_schema(conn)
    selected = tuple(dict.fromkeys(country.upper() for country in countries))
    if not selected:
        raise ValueError("At least one country is required")
    if max_attempts_per_indicator < 1:
        raise ValueError("max_attempts_per_indicator must be at least 1")
    known = {
        row[0]
        for row in conn.execute(
            f"SELECT iso3 FROM country WHERE iso3 IN ({','.join('?' for _ in selected)})",
            selected,
        )
    }
    unknown = sorted(set(selected) - known)
    if unknown:
        raise ValueError(f"Unknown country ISO3 codes: {', '.join(unknown)}")

    last_year = end_year or date.today().year
    fetched_at = _utc_now()
    inserted = 0
    requests = 0
    attempted = 0
    errors: list[dict[str, str]] = []
    urls: list[str] = []
    countries_with_observations: set[str] = set()
    observations_by_indicator: dict[str, int] = {}

    for spec in NEED_INDICATORS:
        url = _world_bank_bulk_url(spec.indicator_code)
        urls.append(url)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "K-Global-Opportunity-Radar/0.1 (+public-data-research)",
                "Accept": "application/zip, application/octet-stream",
            },
        )
        last_error: Exception | None = None
        indicator_inserted = 0
        for _attempt in range(max_attempts_per_indicator):
            if attempted and request_interval_seconds > 0:
                sleeper(request_interval_seconds)
            attempted += 1
            try:
                response = opener(request, timeout=timeout_seconds)
                with response:
                    payload = response.read()
                with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                    member = _world_bank_data_csv_member(archive)
                    with archive.open(member) as raw_csv:
                        text_stream = io.TextIOWrapper(
                            raw_csv,
                            encoding="utf-8-sig",
                            newline="",
                        )
                        reader = csv.reader(text_stream)
                        header: list[str] | None = None
                        for row in reader:
                            if "Country Code" in row and "Indicator Code" in row:
                                header = row
                                break
                        if header is None:
                            raise ValueError(
                                "World Bank CSV header was not found"
                            )
                        column = {
                            name.strip(): index
                            for index, name in enumerate(header)
                        }
                        year_columns = [
                            (index, int(name))
                            for index, name in enumerate(header)
                            if name.isdigit()
                            and start_year <= int(name) <= last_year
                        ]
                        country_index = column["Country Code"]
                        for row in reader:
                            if len(row) <= country_index:
                                continue
                            country = row[country_index].strip().upper()
                            if country not in known:
                                continue
                            for year_index, observation_year in year_columns:
                                if year_index >= len(row):
                                    continue
                                value_text = row[year_index].strip()
                                if not value_text:
                                    continue
                                value = float(value_text)
                                raw_record = {
                                    "countryiso3code": country,
                                    "indicator_code": spec.indicator_code,
                                    "date": str(observation_year),
                                    "value": value,
                                    "bulk_csv_member": member,
                                }
                                conn.execute(
                                    """INSERT INTO development_indicator_observation(
                                           source_type, country_iso3,
                                           indicator_code, indicator_name,
                                           observation_year, value, fetched_at,
                                           source_url, raw_json
                                       ) VALUES (
                                           'WORLD_BANK_WDI', ?, ?, ?, ?, ?, ?, ?, ?
                                       )
                                       ON CONFLICT(
                                           source_type, country_iso3,
                                           indicator_code, observation_year
                                       ) DO UPDATE SET
                                         indicator_name=excluded.indicator_name,
                                         value=excluded.value,
                                         fetched_at=excluded.fetched_at,
                                         source_url=excluded.source_url,
                                         raw_json=excluded.raw_json""",
                                    (
                                        country,
                                        spec.indicator_code,
                                        spec.indicator_name,
                                        observation_year,
                                        value,
                                        fetched_at,
                                        url,
                                        _json(raw_record),
                                    ),
                                )
                                inserted += 1
                                indicator_inserted += 1
                                countries_with_observations.add(country)
                conn.commit()
                requests += 1
                observations_by_indicator[spec.indicator_code] = (
                    indicator_inserted
                )
                last_error = None
                break
            except Exception as exc:
                conn.rollback()
                last_error = exc
        if last_error is not None:
            errors.append(
                {
                    "indicator_code": spec.indicator_code,
                    "error": f"{type(last_error).__name__}: {last_error}",
                }
            )

    return {
        "transport": "bulk_csv_zip",
        "countries": list(selected),
        "countries_with_observations": sorted(countries_with_observations),
        "countries_without_observations": sorted(
            set(selected) - countries_with_observations
        ),
        "start_year": start_year,
        "end_year": last_year,
        "requests": requests,
        "attempted_requests": attempted,
        "observations_upserted": inserted,
        "observations_by_indicator": observations_by_indicator,
        "errors": errors,
        "source_urls": urls,
    }


def _empirical_percentile(value: float, population: list[float]) -> float:
    """Mid-rank empirical percentile, while keeping structural zero at zero."""
    if value <= 0 or not population:
        return 0.0
    less = sum(candidate < value for candidate in population)
    equal = sum(candidate == value for candidate in population)
    return 100.0 * (less + 0.5 * equal) / len(population)


def _midrank_percentile(value: float, population: list[float]) -> float:
    """Mid-rank percentile that permits zero and negative transformed values."""
    if not population:
        return 0.0
    less = sum(candidate < value for candidate in population)
    equal = sum(candidate == value for candidate in population)
    return 100.0 * (less + 0.5 * equal) / len(population)


def _project_source_filter(conn: sqlite3.Connection) -> tuple[str, tuple[object, ...]]:
    has_oecd = bool(
        conn.execute(
            "SELECT EXISTS(SELECT 1 FROM project_master WHERE source_type='OECD_CRS')"
        ).fetchone()[0]
    )
    return (
        ("AND source_type='OECD_CRS'", ())
        if has_oecd
        else ("", ())
    )


def _project_grid(
    conn: sqlite3.Connection,
    *,
    snapshot_year: int,
) -> tuple[dict[tuple[str, str], dict[str, float]], int]:
    source_filter, parameters = _project_source_filter(conn)
    max_year = conn.execute(
        f"SELECT MAX(start_year) FROM project_master WHERE 1=1 {source_filter}",
        parameters,
    ).fetchone()[0]
    data_cutoff = min(snapshot_year, int(max_year)) if max_year is not None else snapshot_year
    rows = conn.execute(
        f"""SELECT country_iso3, sector_code,
                  SUM(CASE WHEN start_year BETWEEN ? AND ? THEN 1 ELSE 0 END) count_3y,
                  SUM(CASE WHEN start_year BETWEEN ? AND ?
                           THEN COALESCE(commitment_amount, 0) ELSE 0 END) amount_3y,
                  SUM(CASE WHEN start_year BETWEEN ? AND ? THEN 1 ELSE 0 END) count_5y,
                  COUNT(DISTINCT CASE WHEN start_year BETWEEN ? AND ?
                                      THEN implementing_agency END) agencies_5y,
                  COUNT(DISTINCT CASE WHEN start_year BETWEEN ? AND ?
                                      THEN start_year END) active_years_5y,
                  SUM(CASE WHEN start_year BETWEEN ? AND ?
                                AND commitment_amount IS NOT NULL THEN 1 ELSE 0 END)
                      amount_observed_3y
           FROM project_master
           WHERE start_year<=? {source_filter}
           GROUP BY country_iso3, sector_code""",
        (
            data_cutoff - 2,
            data_cutoff,
            data_cutoff - 2,
            data_cutoff,
            data_cutoff - 4,
            data_cutoff,
            data_cutoff - 4,
            data_cutoff,
            data_cutoff - 4,
            data_cutoff,
            data_cutoff - 2,
            data_cutoff,
            data_cutoff,
            *parameters,
        ),
    ).fetchall()
    values: dict[tuple[str, str], dict[str, float]] = {}
    for row in rows:
        values[(row["country_iso3"], row["sector_code"])] = {
            "count_3y": float(row["count_3y"] or 0),
            "amount_3y": float(row["amount_3y"] or 0),
            "count_5y": float(row["count_5y"] or 0),
            "agencies_5y": float(row["agencies_5y"] or 0),
            "active_years_5y": float(row["active_years_5y"] or 0),
            "amount_observed_3y": float(row["amount_observed_3y"] or 0),
        }
    return values, data_cutoff


def _save_score(
    conn: sqlite3.Connection,
    *,
    country: str,
    sector: str,
    snapshot_year: int,
    model_code: str,
    score: float | None,
    evidence_status: str,
    data_coverage: float,
    components: dict[str, object],
    caveats: list[str],
    source_urls: list[str] | None = None,
) -> None:
    conn.execute(
        """INSERT INTO opportunity_model_score(
               country_iso3, sector_code, snapshot_year, model_code, model_version,
               score, evidence_status, data_coverage, components_json,
               caveats_json, source_urls_json, created_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(
               country_iso3, sector_code, snapshot_year, model_code, model_version
           ) DO UPDATE SET
             score=excluded.score,
             evidence_status=excluded.evidence_status,
             data_coverage=excluded.data_coverage,
             components_json=excluded.components_json,
             caveats_json=excluded.caveats_json,
             source_urls_json=excluded.source_urls_json,
             created_at=excluded.created_at""",
        (
            country,
            sector,
            snapshot_year,
            model_code,
            MODEL_VERSION,
            score,
            evidence_status,
            max(0.0, min(1.0, data_coverage)),
            _json(components),
            _json(caveats),
            _json(source_urls or []),
            _utc_now(),
        ),
    )


def _score_supply_and_readiness(
    conn: sqlite3.Connection,
    *,
    countries: tuple[str, ...],
    snapshot_year: int,
) -> int:
    grid, data_cutoff = _project_grid(conn, snapshot_year=snapshot_year)
    all_keys = [
        (country, sector)
        for country in {row[0] for row in conn.execute("SELECT iso3 FROM country")}
        for sector in SECTORS
    ]
    metrics = {
        key: grid.get(
            key,
            {
                "count_3y": 0.0,
                "amount_3y": 0.0,
                "count_5y": 0.0,
                "agencies_5y": 0.0,
                "active_years_5y": 0.0,
                "amount_observed_3y": 0.0,
            },
        )
        for key in all_keys
    }
    distributions = {
        name: [value[name] for value in metrics.values()]
        for name in (
            "count_3y",
            "amount_3y",
            "count_5y",
            "agencies_5y",
            "active_years_5y",
        )
    }
    written = 0
    for country in countries:
        for sector in SECTORS:
            value = metrics.get(
                (country, sector),
                {name: 0.0 for name in (*distributions, "amount_observed_3y")},
            )
            count_pct = _empirical_percentile(
                value["count_3y"], distributions["count_3y"]
            )
            amount_pct = _empirical_percentile(
                value["amount_3y"], distributions["amount_3y"]
            )
            has_amount = value["amount_observed_3y"] > 0
            supply_score = (
                0.6 * count_pct + 0.4 * amount_pct if has_amount else count_pct
            )
            _save_score(
                conn,
                country=country,
                sector=sector,
                snapshot_year=snapshot_year,
                model_code="korean_supply_intensity",
                score=supply_score,
                evidence_status="descriptive_only",
                data_coverage=1.0 if has_amount else 0.6,
                components={
                    "data_cutoff_year": data_cutoff,
                    "recent_project_count_3y": value["count_3y"],
                    "recent_commitment_3y": value["amount_3y"],
                    "project_count_percentile": count_pct,
                    "commitment_percentile": amount_pct if has_amount else None,
                },
                caveats=[
                    "This measures Korean ODA supply intensity, not market saturation.",
                    "All-donor OECD data is required before interpreting crowding or whitespace.",
                ],
            )

            count_5_pct = _empirical_percentile(
                value["count_5y"], distributions["count_5y"]
            )
            agency_pct = _empirical_percentile(
                value["agencies_5y"], distributions["agencies_5y"]
            )
            active_year_pct = _empirical_percentile(
                value["active_years_5y"], distributions["active_years_5y"]
            )
            readiness_score = (
                0.45 * count_5_pct + 0.30 * agency_pct + 0.25 * active_year_pct
            )
            _save_score(
                conn,
                country=country,
                sector=sector,
                snapshot_year=snapshot_year,
                model_code="delivery_readiness",
                score=readiness_score,
                evidence_status="descriptive_only",
                data_coverage=1.0,
                components={
                    "data_cutoff_year": data_cutoff,
                    "project_count_5y": value["count_5y"],
                    "agency_diversity_5y": value["agencies_5y"],
                    "active_years_5y": value["active_years_5y"],
                    "project_count_percentile": count_5_pct,
                    "agency_diversity_percentile": agency_pct,
                    "active_years_percentile": active_year_pct,
                    "formula": (
                        "0.45*project_count_percentile + "
                        "0.30*agency_diversity_percentile + "
                        "0.25*active_years_percentile"
                    ),
                },
                caveats=[
                    "Readiness is inferred from delivery history; it does not directly measure procurement or local counterpart capacity."
                ],
            )
            written += 2
    return written


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return bool(
        conn.execute(
            """SELECT EXISTS(
                   SELECT 1 FROM sqlite_master
                   WHERE type='table' AND name=?
               )""",
            (table_name,),
        ).fetchone()[0]
    )


def _score_implementation_feasibility(
    conn: sqlite3.Connection,
    *,
    countries: tuple[str, ...],
    snapshot_year: int,
) -> int:
    """Screen implementation context without inventing a risk-adjusted sum.

    Delivery readiness remains the numeric anchor. Safety, macro context and
    source coverage act as explicit gates/status flags rather than arbitrary
    deductions from that statistically comparable score.
    """
    has_country_profile = _table_exists(conn, "country_profile")
    has_safety = _table_exists(conn, "safety_notice")
    has_coverage = _table_exists(conn, "source_coverage")
    has_kf_partners = _table_exists(conn, "kf_partner_org")
    written = 0
    for country in countries:
        warning = (
            conn.execute(
                """SELECT warning_level, published_at, title, source_url
                   FROM safety_notice
                   WHERE country_iso3=?
                     AND SUBSTR(published_at, 1, 4) <= ?
                   ORDER BY published_at DESC, id DESC LIMIT 1""",
                (country, str(snapshot_year)),
            ).fetchone()
            if has_safety
            else None
        )
        economy = (
            conn.execute(
                """SELECT observed_at, gdp_growth_rate, inflation_rate,
                          unemployment_rate, gdp_per_capita
                   FROM country_profile
                   WHERE country_iso3=? AND profile_type='economy'
                     AND SUBSTR(observed_at, 1, 4) <= ?
                   ORDER BY observed_at DESC LIMIT 1""",
                (country, str(snapshot_year)),
            ).fetchone()
            if has_country_profile
            else None
        )
        coverage = (
            {
                str(row["source_type"]): {
                    "record_count": int(row["record_count"]),
                    "observed_at": str(row["observed_at"]),
                }
                for row in conn.execute(
                    """SELECT source_type, record_count, observed_at
                       FROM source_coverage
                       WHERE country_iso3=? AND source_type IN ('KOICA', 'MOFA')""",
                    (country,),
                )
            }
            if has_coverage
            else {}
        )
        kf_partner_count = (
            int(
                conn.execute(
                    """SELECT COUNT(*) FROM kf_partner_org
                       WHERE country_iso3=?""",
                    (country,),
                ).fetchone()[0]
            )
            if has_kf_partners
            else 0
        )
        source_urls = {
            str(row[0])
            for row in conn.execute(
                """SELECT source_url FROM source_record
                   WHERE country_iso3=? AND source_type='MOFA'
                     AND source_url IS NOT NULL""",
                (country,),
            )
        }
        if warning is not None and warning["source_url"]:
            source_urls.add(str(warning["source_url"]))

        macro_flags: list[str] = []
        if economy is not None:
            if (
                economy["inflation_rate"] is not None
                and float(economy["inflation_rate"]) >= 10.0
            ):
                macro_flags.append("high_inflation_review")
            if (
                economy["gdp_growth_rate"] is not None
                and float(economy["gdp_growth_rate"]) < 0.0
            ):
                macro_flags.append("negative_growth_review")
            if (
                economy["unemployment_rate"] is not None
                and float(economy["unemployment_rate"]) >= 10.0
            ):
                macro_flags.append("high_unemployment_review")

        for sector in SECTORS:
            readiness_row = conn.execute(
                """SELECT score, data_coverage, components_json
                   FROM opportunity_model_score
                   WHERE country_iso3=? AND sector_code=?
                     AND snapshot_year=? AND model_code='delivery_readiness'
                     AND model_version=?""",
                (country, sector, snapshot_year, MODEL_VERSION),
            ).fetchone()
            readiness = (
                float(readiness_row["score"])
                if readiness_row is not None
                and readiness_row["score"] is not None
                else None
            )
            availability = {
                "delivery_readiness": readiness is not None,
                "safety_notice": warning is not None,
                "economy_profile": economy is not None,
                "koica_coverage": "KOICA" in coverage,
                "mofa_coverage": "MOFA" in coverage,
            }
            data_coverage = sum(availability.values()) / len(availability)
            warning_level = (
                int(warning["warning_level"]) if warning is not None else None
            )
            if readiness is None:
                status = "insufficient_context"
                score = None
                evidence_status = "insufficient_data"
            elif warning_level is not None and warning_level >= 4:
                status = "blocked_by_safety"
                score = None
                evidence_status = "rule_based_evidence"
            elif warning is None or economy is None:
                status = "insufficient_context"
                score = None
                evidence_status = "insufficient_data"
            elif warning_level is not None and warning_level >= 3:
                status = "manual_risk_review"
                score = readiness
                evidence_status = "rule_based_evidence"
            elif macro_flags:
                status = "manual_economic_review"
                score = readiness
                evidence_status = "rule_based_evidence"
            elif readiness >= 50:
                status = "screen_ready"
                score = readiness
                evidence_status = "rule_based_evidence"
            else:
                status = "capacity_building_needed"
                score = readiness
                evidence_status = "rule_based_evidence"

            _save_score(
                conn,
                country=country,
                sector=sector,
                snapshot_year=snapshot_year,
                model_code="implementation_feasibility",
                score=score,
                evidence_status=evidence_status,
                data_coverage=data_coverage,
                components={
                    "implementation_status": status,
                    "numeric_anchor": "delivery_readiness",
                    "delivery_readiness_score": readiness,
                    "delivery_readiness_components": (
                        json.loads(readiness_row["components_json"])
                        if readiness_row is not None
                        else None
                    ),
                    "warning_level": warning_level,
                    "warning_title": (
                        str(warning["title"]) if warning is not None else None
                    ),
                    "economy_profile": (
                        {
                            "observed_at": economy["observed_at"],
                            "gdp_growth_rate": economy["gdp_growth_rate"],
                            "inflation_rate": economy["inflation_rate"],
                            "unemployment_rate": economy["unemployment_rate"],
                            "gdp_per_capita": economy["gdp_per_capita"],
                        }
                        if economy is not None
                        else None
                    ),
                    "macro_review_flags": macro_flags,
                    "source_coverage": coverage,
                    "context_availability": availability,
                    "kf_partner_org_count": (
                        kf_partner_count
                        if sector in {"korean_studies", "culture_content"}
                        else None
                    ),
                    "gating_rule": (
                        "safety>=4:block; safety>=3:manual risk review; "
                        "macro flag:manual economic review; "
                        "otherwise readiness>=50:screen ready"
                    ),
                },
                caveats=[
                    "The numeric value is delivery-history readiness, not an arbitrary weighted average of incomparable risks.",
                    "Travel warnings may apply only to parts of a country and trigger review rather than an automatic penalty below level 4.",
                    "Macro thresholds are screening flags, not causal estimates of project failure.",
                    "Legal, procurement and named counterpart due diligence still require project-level evidence.",
                ],
                source_urls=sorted(source_urls),
            )
            written += 1
    return written


def _score_all_donor_supply(
    conn: sqlite3.Connection,
    *,
    countries: tuple[str, ...],
    snapshot_year: int,
) -> int:
    metrics, data_cutoff = all_donor_supply_metrics(
        conn, snapshot_year=snapshot_year, window_years=3
    )
    source_urls = [
        str(row[0])
        for row in conn.execute(
            """SELECT DISTINCT source_url FROM donor_activity_aggregate
               WHERE reporting_year BETWEEN ? AND ? AND source_url IS NOT NULL
               ORDER BY source_url""",
            (data_cutoff - 2, data_cutoff),
        )
    ]
    written = 0
    for country in countries:
        for sector in SECTORS:
            value = metrics.get((country, sector))
            if value is None:
                for model_code in (
                    "all_donor_saturation",
                    "korea_share_of_donor_supply",
                ):
                    _save_score(
                        conn,
                        country=country,
                        sector=sector,
                        snapshot_year=snapshot_year,
                        model_code=model_code,
                        score=None,
                        evidence_status="insufficient_data",
                        data_coverage=0.0,
                        components={"data_cutoff_year": data_cutoff},
                        caveats=[
                            "All-donor OECD CRS aggregates are not loaded for this country."
                        ],
                    )
                    written += 1
                continue
            common = {
                "data_cutoff_year": data_cutoff,
                "window_years": 3,
                "total_volume_usd_m": value["total_volume_usd_m"],
                "total_commitment_usd_m": value["total_commitment_usd_m"],
                "total_disbursement_usd_m": value["total_disbursement_usd_m"],
                "volume_basis": (
                    "disbursement"
                    if value["volume_basis"] == 1.0 else "commitment"
                ),
                "donor_count": value["donor_count"],
                "hhi_0_1": value["hhi_0_1"],
                "donor_diversity_0_100": value["donor_diversity_0_100"],
                "volume_percentile": value["volume_percentile"],
                "donor_count_percentile": value["donor_count_percentile"],
                "korea_volume_usd_m": value["korea_volume_usd_m"],
                "korea_share_0_100": value["korea_share_0_100"],
            }
            _save_score(
                conn,
                country=country,
                sector=sector,
                snapshot_year=snapshot_year,
                model_code="all_donor_saturation",
                score=value["saturation_score"],
                evidence_status="descriptive_only",
                data_coverage=1.0,
                components={
                    **common,
                    "formula": (
                        "0.60*all_donor_volume_percentile + "
                        "0.25*donor_count_percentile + "
                        "0.15*donor_diversity"
                    ),
                },
                caveats=[
                    "This is a relative OECD CRS supply/crowding screen, not a measure of private-sector competition.",
                    "CRS reporting revisions and purpose-code mapping can change the score.",
                ],
                source_urls=source_urls,
            )
            _save_score(
                conn,
                country=country,
                sector=sector,
                snapshot_year=snapshot_year,
                model_code="korea_share_of_donor_supply",
                score=value["korea_share_0_100"],
                evidence_status="descriptive_only",
                data_coverage=1.0,
                components=common,
                caveats=[
                    "The share uses positive OECD CRS disbursements, or commitments when no disbursement is available."
                ],
                source_urls=source_urls,
            )
            written += 2
    return written


def _score_all_donor_momentum(
    conn: sqlite3.Connection,
    *,
    countries: tuple[str, ...],
    snapshot_year: int,
) -> int:
    metrics, data_cutoff = donor_supply_momentum_metrics(
        conn,
        snapshot_year=snapshot_year,
        window_years=6,
    )
    source_urls = [
        str(row[0])
        for row in conn.execute(
            """SELECT DISTINCT source_url FROM donor_activity_aggregate
               WHERE reporting_year BETWEEN ? AND ? AND source_url IS NOT NULL
               ORDER BY source_url""",
            (data_cutoff - 5, data_cutoff),
        )
    ]
    written = 0
    for country in countries:
        for sector in SECTORS:
            value = metrics.get((country, sector))
            if value is None:
                _save_score(
                    conn,
                    country=country,
                    sector=sector,
                    snapshot_year=snapshot_year,
                    model_code="all_donor_momentum",
                    score=None,
                    evidence_status="insufficient_data",
                    data_coverage=0.0,
                    components={"data_cutoff_year": data_cutoff},
                    caveats=[
                        "Six-year OECD CRS aggregates are not loaded for this country."
                    ],
                )
                written += 1
                continue
            _save_score(
                conn,
                country=country,
                sector=sector,
                snapshot_year=snapshot_year,
                model_code="all_donor_momentum",
                score=float(value["momentum_score"]),
                evidence_status="descriptive_only",
                data_coverage=1.0,
                components={
                    **value,
                    "formula": (
                        "0.70*log_volume_slope_percentile + "
                        "0.30*recent_two_year_change_percentile"
                    ),
                },
                caveats=[
                    "Momentum describes the direction of reported OECD public and ODA supply, not future demand.",
                    "Only six annual observations are available; Mann-Kendall p-values have low power and are diagnostic.",
                    "A zero year is treated as no reported mapped activity, not as a missing-value imputation.",
                ],
                source_urls=source_urls,
            )
            written += 1
    return written


def _score_need(
    conn: sqlite3.Connection,
    *,
    countries: tuple[str, ...],
    snapshot_year: int,
) -> int:
    specs_by_sector: dict[str, list[NeedIndicator]] = {}
    for spec in NEED_INDICATORS:
        specs_by_sector.setdefault(spec.sector_code, []).append(spec)

    latest_by_indicator: dict[str, dict[str, sqlite3.Row]] = {}
    transformed_population: dict[str, list[float]] = {}
    for spec in NEED_INDICATORS:
        rows = conn.execute(
            """WITH ranked AS (
                   SELECT country_iso3, observation_year, value, source_url,
                          ROW_NUMBER() OVER (
                              PARTITION BY country_iso3
                              ORDER BY observation_year DESC
                          ) AS row_number
                   FROM development_indicator_observation
                   WHERE source_type='WORLD_BANK_WDI'
                     AND indicator_code=?
                     AND observation_year BETWEEN ? AND ?
               )
               SELECT country_iso3, observation_year, value, source_url
               FROM ranked WHERE row_number=1""",
            (
                spec.indicator_code,
                snapshot_year - MAX_INDICATOR_AGE_YEARS,
                snapshot_year,
            ),
        ).fetchall()
        latest_by_indicator[spec.indicator_code] = {
            str(row["country_iso3"]): row for row in rows
        }
        transformed_population[spec.indicator_code] = [
            (
                float(row["value"])
                if spec.need_direction == "higher_value_more_need"
                else -float(row["value"])
            )
            for row in rows
        ]

    written = 0
    for country in countries:
        for sector in SECTORS:
            specs = specs_by_sector.get(sector, [])
            if not specs:
                _save_score(
                    conn,
                    country=country,
                    sector=sector,
                    snapshot_year=snapshot_year,
                    model_code="unmet_need",
                    score=None,
                    evidence_status="insufficient_data",
                    data_coverage=0.0,
                    components={"required_indicator_contract": "not_defined"},
                    caveats=[
                        "No direct, sector-specific outcome indicator has been approved for this sector."
                    ],
                )
                written += 1
                continue

            components: list[dict[str, object]] = []
            observed_components: list[tuple[str, float, float]] = []
            source_urls: set[str] = set()
            weighted_percentiles = 0.0
            observed_weight = 0.0
            weighted_freshness = 0.0
            for spec in specs:
                row = latest_by_indicator[spec.indicator_code].get(country)
                if row is None:
                    components.append(
                        {
                            "indicator_code": spec.indicator_code,
                            "indicator_name": spec.indicator_name,
                            "available": False,
                            "need_direction": spec.need_direction,
                            "weight": spec.weight,
                        }
                    )
                    continue
                observed = float(row["value"])
                transformed = (
                    observed
                    if spec.need_direction == "higher_value_more_need"
                    else -observed
                )
                percentile = _midrank_percentile(
                    transformed,
                    transformed_population[spec.indicator_code],
                )
                age = max(0, snapshot_year - int(row["observation_year"]))
                freshness = 1.0 if age <= 2 else 0.7 if age <= 5 else 0.4
                weighted_percentiles += spec.weight * percentile
                observed_weight += spec.weight
                weighted_freshness += spec.weight * freshness
                observed_components.append(
                    (spec.indicator_code, percentile, spec.weight)
                )
                if row["source_url"]:
                    source_urls.add(str(row["source_url"]))
                components.append(
                    {
                        "indicator_code": spec.indicator_code,
                        "indicator_name": spec.indicator_name,
                        "available": True,
                        "observation_year": int(row["observation_year"]),
                        "observed_value": observed,
                        "need_direction": spec.need_direction,
                        "need_percentile": percentile,
                        "comparison_country_count": len(
                            transformed_population[spec.indicator_code]
                        ),
                        "freshness_weight": freshness,
                        "weight": spec.weight,
                    }
                )
            observed_count = sum(bool(item["available"]) for item in components)
            total_weight = sum(spec.weight for spec in specs)
            if observed_count < 2 or observed_weight <= 0:
                _save_score(
                    conn,
                    country=country,
                    sector=sector,
                    snapshot_year=snapshot_year,
                    model_code="unmet_need",
                    score=None,
                    evidence_status="insufficient_data",
                    data_coverage=(
                        observed_weight / total_weight if total_weight else 0.0
                    ),
                    components={
                        "minimum_required_indicators": 2,
                        "observed_indicator_count": observed_count,
                        "indicators": components,
                    },
                    caveats=[
                        "At least two current sector indicators are required for a composite need score."
                    ],
                    source_urls=sorted(source_urls),
                )
                written += 1
                continue
            need_score = weighted_percentiles / observed_weight
            completeness = observed_weight / total_weight if total_weight else 0.0
            average_freshness = weighted_freshness / observed_weight
            leave_one_out_scores: list[dict[str, object]] = []
            if observed_count >= 3:
                for indicator_code, percentile, weight in observed_components:
                    remaining_weight = observed_weight - weight
                    if remaining_weight <= 0:
                        continue
                    leave_one_out_scores.append(
                        {
                            "excluded_indicator_code": indicator_code,
                            "score": (
                                weighted_percentiles - weight * percentile
                            )
                            / remaining_weight,
                        }
                    )
            sensitivity_scores = [
                float(item["score"]) for item in leave_one_out_scores
            ]
            sensitivity = (
                {
                    "method": "leave_one_indicator_out",
                    "scores": leave_one_out_scores,
                    "minimum_score": min(sensitivity_scores),
                    "maximum_score": max(sensitivity_scores),
                    "range": max(sensitivity_scores) - min(sensitivity_scores),
                    "high_need_threshold": HIGH_NEED_THRESHOLD,
                    "threshold_classification_stable": all(
                        (score >= HIGH_NEED_THRESHOLD)
                        == (need_score >= HIGH_NEED_THRESHOLD)
                        for score in sensitivity_scores
                    ),
                }
                if sensitivity_scores
                else {
                    "method": "leave_one_indicator_out",
                    "scores": [],
                    "available": False,
                    "reason": "At least three observed indicators are required.",
                }
            )
            _save_score(
                conn,
                country=country,
                sector=sector,
                snapshot_year=snapshot_year,
                model_code="unmet_need",
                score=need_score,
                evidence_status="descriptive_only",
                data_coverage=completeness * average_freshness,
                components={
                    "method": "weighted_mean_of_global_need_percentiles",
                    "minimum_required_indicators": 2,
                    "observed_indicator_count": observed_count,
                    "indicator_completeness": completeness,
                    "average_freshness": average_freshness,
                    "indicators": components,
                    "sensitivity": sensitivity,
                },
                caveats=[
                    "This is relative need among countries with recent observations, not an absolute policy target gap.",
                    "Correlated indicators and uneven reporting can affect the composite percentile.",
                    "The score is a screening statistic, not proof of fundable demand or causal impact.",
                ],
                source_urls=sorted(source_urls),
            )
            written += 1
    return written


def _score_policy_fit(
    conn: sqlite3.Connection,
    *,
    countries: tuple[str, ...],
    snapshot_year: int,
) -> int:
    sync_signal_events(conn)
    classification_stats = classify_policy_evidence(conn)
    written = 0
    for country in countries:
        for sector in SECTORS:
            rows = conn.execute(
                """SELECT s.event_tier AS source_event_tier, s.source_type,
                          s.confidence AS source_confidence,
                          s.organizations_json, s.source_url,
                          p.event_tier AS policy_tier,
                          p.inferred_event_type,
                          p.review_status,
                          p.confidence AS policy_confidence
                   FROM signal_event s
                   LEFT JOIN policy_evidence_classification p
                     ON p.evidence_id=s.evidence_id
                   WHERE country_iso3=? AND sector_code=? AND eligible_predictor=1
                     AND event_year BETWEEN ? AND ?""",
                (country, sector, snapshot_year - 2, snapshot_year),
            ).fetchall()
            if not rows:
                _save_score(
                    conn,
                    country=country,
                    sector=sector,
                    snapshot_year=snapshot_year,
                    model_code="policy_fit",
                    score=None,
                    evidence_status="insufficient_data",
                    data_coverage=0.0,
                    components={"recent_evidence_count_3y": 0},
                    caveats=[
                        "Absence of extracted policy evidence is treated as missing data, not zero policy fit."
                    ],
                )
                written += 1
                continue
            approved = [
                row
                for row in rows
                if row["policy_tier"] in {"A", "B"}
                and row["review_status"]
                in {"source_labeled", "human_approved"}
            ]
            review_candidates = [
                row
                for row in rows
                if row["review_status"] == "review_required"
            ]
            tier_weights = {"A": 1.0, "B": 0.6}
            weighted_ab = sum(
                float(row["policy_confidence"])
                * tier_weights[str(row["policy_tier"])]
                for row in approved
            )
            sources = {str(row["source_type"]) for row in approved}
            organizations: set[str] = set()
            for row in approved:
                try:
                    organizations.update(json.loads(row["organizations_json"] or "[]"))
                except (TypeError, json.JSONDecodeError):
                    pass
            if weighted_ab <= 0:
                _save_score(
                    conn,
                    country=country,
                    sector=sector,
                    snapshot_year=snapshot_year,
                    model_code="policy_fit",
                    score=None,
                    evidence_status="insufficient_data",
                    data_coverage=min(1.0, len(sources) / 3.0),
                    components={
                        "recent_evidence_count_3y": len(rows),
                        "approved_tier_ab_count": 0,
                        "review_required_count": len(review_candidates),
                        "tier_ab_weighted_evidence": 0.0,
                        "classification_run_counts": classification_stats,
                    },
                    caveats=[
                        "No source-labelled or human-approved Tier A/B evidence is present.",
                        "Pattern-inferred candidates are excluded until human review.",
                    ],
                    source_urls=sorted(
                        {str(row["source_url"]) for row in rows if row["source_url"]}
                    ),
                )
                written += 1
                continue
            # Fixed ceilings make the evidence score reproducible across runs.
            intensity = 100.0 * min(1.0, weighted_ab / 3.0)
            source_diversity = 100.0 * min(1.0, len(sources) / 3.0)
            partner_diversity = 100.0 * min(1.0, len(organizations) / 5.0)
            score = 0.6 * intensity + 0.2 * source_diversity + 0.2 * partner_diversity
            _save_score(
                conn,
                country=country,
                sector=sector,
                snapshot_year=snapshot_year,
                model_code="policy_fit",
                score=score,
                evidence_status="rule_based_evidence",
                data_coverage=min(1.0, len(sources) / 3.0),
                components={
                    "approved_tier_ab_count": len(approved),
                    "review_required_count": len(review_candidates),
                    "tier_ab_weighted_evidence": weighted_ab,
                    "source_diversity": len(sources),
                    "partner_diversity": len(organizations),
                    "approved_event_types": sorted(
                        {
                            str(row["inferred_event_type"])
                            for row in approved
                            if row["inferred_event_type"]
                        }
                    ),
                    "formula": (
                        "0.60*tier_ab_intensity + 0.20*source_diversity + "
                        "0.20*partner_diversity"
                    ),
                },
                caveats=[
                    "Policy fit is evidence-coded and has not passed outcome-based predictive validation."
                ],
                source_urls=sorted(
                    {str(row["source_url"]) for row in rows if row["source_url"]}
                ),
            )
            written += 1
    return written


def _score_continuity(
    conn: sqlite3.Connection,
    *,
    countries: tuple[str, ...],
    snapshot_year: int,
    horizon_years: int,
) -> int:
    candidates = predict_current_candidates(
        conn,
        horizon_years=horizon_years,
        snapshot_year=snapshot_year,
        countries=countries,
        limit=len(countries) * len(SECTORS),
    )
    indexed = {
        (row["country_iso3"], row["sector_code"]): row for row in candidates
    }
    written = 0
    for country in countries:
        for sector in SECTORS:
            row = indexed.get((country, sector))
            if row is None:
                _save_score(
                    conn,
                    country=country,
                    sector=sector,
                    snapshot_year=snapshot_year,
                    model_code="cooperation_continuity",
                    score=None,
                    evidence_status="not_validated",
                    data_coverage=0.0,
                    components={"horizon_years": horizon_years},
                    caveats=[
                        "No chronologically validated continuity model is available."
                    ],
                )
            else:
                _save_score(
                    conn,
                    country=country,
                    sector=sector,
                    snapshot_year=snapshot_year,
                    model_code="cooperation_continuity",
                    score=100.0 * float(row["recommended_probability"]),
                    evidence_status="validated_predictive",
                    data_coverage=float(row["data_coverage"]),
                    components={
                        "validation_run_id": row["validation_run_id"],
                        "horizon_years": horizon_years,
                        "validated_signal_type": row["validated_signal_type"],
                        "historical_recurrence_probability": row[
                            "historical_recurrence_probability"
                        ],
                        "structural_probability": row["structural_probability"],
                        "prior_project_count_3y": row["prior_project_count_3y"],
                        "years_since_last_project": row["years_since_last_project"],
                    },
                    caveats=[
                        "This predicts project continuation/recurrence, not unmet development need.",
                        "Diplomatic variables are omitted when their incremental validation fails.",
                    ],
                )
            written += 1
    return written


def _latest_scores(
    conn: sqlite3.Connection,
    *,
    countries: tuple[str, ...],
    snapshot_year: int,
) -> dict[tuple[str, str], dict[str, sqlite3.Row]]:
    placeholders = ",".join("?" for _ in countries)
    rows = conn.execute(
        f"""SELECT * FROM opportunity_model_score
            WHERE model_version=? AND snapshot_year=?
              AND country_iso3 IN ({placeholders})""",
        (MODEL_VERSION, snapshot_year, *countries),
    ).fetchall()
    result: dict[tuple[str, str], dict[str, sqlite3.Row]] = {}
    for row in rows:
        result.setdefault((row["country_iso3"], row["sector_code"]), {})[
            row["model_code"]
        ] = row
    return result


def build_candidate_profiles(
    conn: sqlite3.Connection,
    *,
    countries: Iterable[str],
    snapshot_year: int,
) -> list[dict[str, object]]:
    """Create transparent candidate types without manufacturing a total score."""
    selected = tuple(dict.fromkeys(country.upper() for country in countries))
    scores = _latest_scores(
        conn, countries=selected, snapshot_year=snapshot_year
    )
    result: list[dict[str, object]] = []
    for country in selected:
        for sector in SECTORS:
            model_rows = scores.get((country, sector), {})

            def value(code: str) -> float | None:
                row = model_rows.get(code)
                return None if row is None or row["score"] is None else float(row["score"])

            def components(code: str) -> dict[str, object]:
                row = model_rows.get(code)
                if row is None:
                    return {}
                try:
                    return json.loads(row["components_json"] or "{}")
                except (TypeError, json.JSONDecodeError):
                    return {}

            continuity = value("cooperation_continuity")
            need = value("unmet_need")
            supply = value("korean_supply_intensity")
            saturation = value("all_donor_saturation")
            momentum = value("all_donor_momentum")
            korea_share = value("korea_share_of_donor_supply")
            readiness = value("delivery_readiness")
            implementation = value("implementation_feasibility")
            implementation_status = str(
                components("implementation_feasibility").get(
                    "implementation_status",
                    "insufficient_context",
                )
            )
            policy = value("policy_fit")
            rationale: list[str] = []
            if need is None:
                candidate_type = "needs_demand_data"
                decision_status = "hold"
                rationale.append("A sector-specific unmet-need indicator is unavailable.")
            elif saturation is None:
                candidate_type = "needs_supply_data"
                decision_status = "hold"
                rationale.append("All-donor OECD CRS supply data is unavailable.")
            elif (
                need >= HIGH_NEED_THRESHOLD
                and continuity is not None
                and continuity >= 60
                and implementation is not None
                and implementation >= 50
                and implementation_status == "screen_ready"
                and saturation < 70
            ):
                candidate_type = "priority_expansion"
                decision_status = "screen"
                rationale.append(
                    "High outcome gap is paired with validated continuity and delivery history."
                )
            elif need >= HIGH_NEED_THRESHOLD and saturation < 40:
                candidate_type = "potential_whitespace"
                decision_status = "research"
                rationale.append(
                    "Outcome gap is high while observed all-donor supply is low."
                )
            elif (
                need >= HIGH_NEED_THRESHOLD
                and saturation >= 70
                and (korea_share or 0.0) < 10
            ):
                candidate_type = "competitive_market"
                decision_status = "research"
                rationale.append(
                    "Outcome gap is high, but many donors are active and Korea has a low supply share."
                )
            elif continuity is not None and continuity >= 60:
                candidate_type = "continuation_candidate"
                decision_status = "screen"
                rationale.append(
                    "Continuation probability is high, but unmet need is not high enough for priority expansion."
                )
            else:
                candidate_type = "monitor"
                decision_status = "monitor"
                rationale.append("No provisional decision rule is strongly activated.")
            if policy is None:
                rationale.append("Policy-fit evidence is missing and must be manually checked.")
            if implementation_status == "blocked_by_safety":
                decision_status = "hold"
                rationale.append(
                    "Implementation is blocked by the current safety gate."
                )
            elif implementation_status in {
                "manual_risk_review",
                "manual_economic_review",
            }:
                if decision_status == "screen":
                    decision_status = "review"
                rationale.append(
                    "Implementation context requires explicit risk review."
                )
            elif implementation_status == "insufficient_context":
                if decision_status == "screen":
                    decision_status = "hold"
                rationale.append(
                    "Implementation context is incomplete; delivery history alone is insufficient."
                )
            conn.execute(
                """INSERT INTO opportunity_candidate_profile(
                       country_iso3, sector_code, snapshot_year, profile_version,
                       continuity_score, unmet_need_score, korean_supply_intensity,
                       all_donor_saturation, all_donor_momentum,
                       korea_supply_share, readiness_score,
                       implementation_feasibility_score,
                       implementation_status, policy_fit_score, decision_status,
                       candidate_type, rationale_json, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(
                       country_iso3, sector_code, snapshot_year, profile_version
                   ) DO UPDATE SET
                     continuity_score=excluded.continuity_score,
                     unmet_need_score=excluded.unmet_need_score,
                     korean_supply_intensity=excluded.korean_supply_intensity,
                     all_donor_saturation=excluded.all_donor_saturation,
                     all_donor_momentum=excluded.all_donor_momentum,
                     korea_supply_share=excluded.korea_supply_share,
                     readiness_score=excluded.readiness_score,
                     implementation_feasibility_score=
                       excluded.implementation_feasibility_score,
                     implementation_status=excluded.implementation_status,
                     policy_fit_score=excluded.policy_fit_score,
                     decision_status=excluded.decision_status,
                     candidate_type=excluded.candidate_type,
                     rationale_json=excluded.rationale_json,
                     created_at=excluded.created_at""",
                (
                    country,
                    sector,
                    snapshot_year,
                    PROFILE_VERSION,
                    continuity,
                    need,
                    supply,
                    saturation,
                    momentum,
                    korea_share,
                    readiness,
                    implementation,
                    implementation_status,
                    policy,
                    decision_status,
                    candidate_type,
                    _json(rationale),
                    _utc_now(),
                ),
            )
            result.append(
                {
                    "country_iso3": country,
                    "sector_code": sector,
                    "candidate_type": candidate_type,
                    "decision_status": decision_status,
                    "continuity_score": continuity,
                    "unmet_need_score": need,
                    "korean_supply_intensity": supply,
                    "all_donor_saturation": saturation,
                    "all_donor_momentum": momentum,
                    "korea_supply_share": korea_share,
                    "readiness_score": readiness,
                    "implementation_feasibility_score": implementation,
                    "implementation_status": implementation_status,
                    "policy_fit_score": policy,
                    "rationale": rationale,
                }
            )
    conn.commit()
    priority = {
        "priority_expansion": 0,
        "potential_whitespace": 1,
        "continuation_candidate": 2,
        "competitive_market": 3,
        "monitor": 4,
        "needs_supply_data": 5,
        "needs_demand_data": 6,
    }
    result.sort(
        key=lambda row: (
            priority[row["candidate_type"]],
            -(row["unmet_need_score"] or -1),
            -(row["continuity_score"] or -1),
        )
    )
    return result


def run_opportunity_models(
    conn: sqlite3.Connection,
    *,
    countries: Iterable[str],
    snapshot_year: int | None = None,
    horizon_years: int = 2,
) -> dict[str, object]:
    """Run separated models and return transparent candidate profiles."""
    ensure_opportunity_model_schema(conn)
    selected = tuple(dict.fromkeys(country.upper() for country in countries))
    if not selected:
        raise ValueError("At least one country is required")
    target_year = snapshot_year or date.today().year
    counts = {
        "continuity": _score_continuity(
            conn,
            countries=selected,
            snapshot_year=target_year,
            horizon_years=horizon_years,
        ),
        "supply_and_readiness": _score_supply_and_readiness(
            conn, countries=selected, snapshot_year=target_year
        ),
        "implementation_feasibility": _score_implementation_feasibility(
            conn,
            countries=selected,
            snapshot_year=target_year,
        ),
        "all_donor_supply": _score_all_donor_supply(
            conn, countries=selected, snapshot_year=target_year
        ),
        "all_donor_momentum": _score_all_donor_momentum(
            conn, countries=selected, snapshot_year=target_year
        ),
        "unmet_need": _score_need(
            conn, countries=selected, snapshot_year=target_year
        ),
        "policy_fit": _score_policy_fit(
            conn, countries=selected, snapshot_year=target_year
        ),
    }
    conn.commit()
    profiles = build_candidate_profiles(
        conn, countries=selected, snapshot_year=target_year
    )
    status_counts: dict[str, int] = {}
    placeholders = ",".join("?" for _ in selected)
    for row in conn.execute(
        f"""SELECT evidence_status, COUNT(*)
            FROM opportunity_model_score
            WHERE model_version=? AND snapshot_year=?
              AND country_iso3 IN ({placeholders})
            GROUP BY evidence_status""",
        (MODEL_VERSION, target_year, *selected),
    ):
        status_counts[str(row[0])] = int(row[1])
    indicator_summary = [
        dict(row)
        for row in conn.execute(
            f"""SELECT indicator_code, COUNT(*) observation_count,
                       MIN(observation_year) first_year,
                       MAX(observation_year) latest_year
                FROM development_indicator_observation
                WHERE source_type='WORLD_BANK_WDI'
                  AND country_iso3 IN ({placeholders})
                GROUP BY indicator_code ORDER BY indicator_code""",
            selected,
        )
    ]
    comparison_indicator_summary = [
        dict(row)
        for row in conn.execute(
            """SELECT indicator_code,
                      COUNT(DISTINCT country_iso3) country_count,
                      COUNT(*) observation_count,
                      MIN(observation_year) first_year,
                      MAX(observation_year) latest_year
               FROM development_indicator_observation
               WHERE source_type='WORLD_BANK_WDI'
               GROUP BY indicator_code ORDER BY indicator_code"""
        )
    ]
    donor_summary_row = conn.execute(
        """SELECT COUNT(*) aggregate_group_count,
                  COUNT(DISTINCT donor_code) donor_count,
                  COUNT(DISTINCT recipient_iso3) recipient_count,
                  MIN(reporting_year) first_year,
                  MAX(reporting_year) latest_year
           FROM donor_activity_aggregate"""
    ).fetchone()
    return {
        "model_version": MODEL_VERSION,
        "profile_version": PROFILE_VERSION,
        "snapshot_year": target_year,
        "countries": list(selected),
        "written": counts,
        "evidence_status_counts": status_counts,
        "development_indicator_summary": indicator_summary,
        "comparison_indicator_summary": comparison_indicator_summary,
        "all_donor_crs_summary": dict(donor_summary_row),
        "profiles": profiles,
    }
