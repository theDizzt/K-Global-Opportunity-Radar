from __future__ import annotations

import csv
import io
import math
import re
import sqlite3
import statistics
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import chain
from pathlib import Path
from typing import Iterable, TextIO

from .project_history import FIELD_ALIASES, _normalized_header, sector_from_purpose
from .taxonomy_v2 import SECTORS


DONOR_SUPPLY_SCHEMA = """
CREATE TABLE IF NOT EXISTS donor_activity_aggregate (
    reporting_year INTEGER NOT NULL,
    donor_code TEXT NOT NULL,
    donor_name TEXT,
    recipient_iso3 TEXT NOT NULL,
    recipient_name TEXT,
    sector_code TEXT NOT NULL REFERENCES sector(code),
    reporting_row_count INTEGER NOT NULL,
    commitment_usd_m REAL NOT NULL,
    disbursement_usd_m REAL NOT NULL,
    source_file TEXT NOT NULL,
    source_url TEXT,
    imported_at TEXT NOT NULL,
    PRIMARY KEY(reporting_year, donor_code, recipient_iso3, sector_code)
);

CREATE INDEX IF NOT EXISTS idx_donor_supply_recipient
ON donor_activity_aggregate(recipient_iso3, sector_code, reporting_year);
CREATE INDEX IF NOT EXISTS idx_donor_supply_year
ON donor_activity_aggregate(reporting_year, sector_code);
"""


def ensure_donor_supply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(DONOR_SUPPLY_SCHEMA)
    if conn.execute(
        "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='country')"
    ).fetchone()[0]:
        conn.execute(
            """INSERT OR IGNORE INTO country(
                   iso3, name_ko, name_en, region_code
               )
               SELECT recipient_iso3,
                      MAX(COALESCE(NULLIF(recipient_name, ''), recipient_iso3)),
                      MAX(COALESCE(NULLIF(recipient_name, ''), recipient_iso3)),
                      'UNKNOWN'
               FROM donor_activity_aggregate
               GROUP BY recipient_iso3"""
        )
    conn.commit()


def _number(value: str | None) -> float:
    if value in {None, ""}:
        return 0.0
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return 0.0


def _resolve_column(fieldnames: Iterable[str], aliases: Iterable[str]) -> str | None:
    normalized = {_normalized_header(name): name for name in fieldnames}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def _open_activity_file(path: Path) -> tuple[TextIO, zipfile.ZipFile | None]:
    if path.suffix.casefold() != ".zip":
        return (
            path.open(
                encoding="utf-8-sig", errors="replace", newline=""
            ),
            None,
        )
    archive = zipfile.ZipFile(path)
    names = [
        name
        for name in archive.namelist()
        if name.casefold().endswith((".txt", ".csv"))
    ]
    if len(names) != 1:
        archive.close()
        raise ValueError("OECD CRS ZIP must contain exactly one CSV or TXT file")
    binary = archive.open(names[0])
    return (
        io.TextIOWrapper(
            binary, encoding="utf-8-sig", errors="replace", newline=""
        ),
        archive,
    )


def load_all_donor_crs_file(
    conn: sqlite3.Connection,
    path: str | Path,
    *,
    source_url: str | None = None,
    recipient_filter: Iterable[str] | None = None,
) -> dict[str, object]:
    """Stream an OECD CRS file into donor-country-sector-year aggregates.

    Existing aggregates for every reporting year found in the file are
    replaced in one transaction. This makes a repeated import idempotent.
    """
    ensure_donor_supply_schema(conn)
    path = Path(path)
    selected = (
        {value.upper() for value in recipient_filter}
        if recipient_filter is not None
        else None
    )
    stats: dict[str, object] = {
        "source_file": path.name,
        "rows_read": 0,
        "rows_aggregated": 0,
        "skipped_aggregate_recipient": 0,
        "skipped_recipient_filter": 0,
        "skipped_donor": 0,
        "skipped_sector": 0,
        "skipped_year": 0,
        "aggregate_groups": 0,
        "years": [],
    }
    aggregates: dict[
        tuple[int, str, str, str],
        dict[str, object],
    ] = {}
    handle, archive = _open_activity_file(path)
    try:
        header = handle.readline()
        delimiter = "|" if header.count("|") > header.count(",") else ","
        reader = csv.DictReader(chain((header,), handle), delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError("OECD CRS file has no header")
        columns = {
            field: _resolve_column(reader.fieldnames, aliases)
            for field, aliases in FIELD_ALIASES.items()
        }
        columns["donor_name"] = _resolve_column(
            reader.fieldnames, ("donorname", "providername")
        )
        columns["disbursement"] = _resolve_column(
            reader.fieldnames,
            ("usddisbursement", "disbursement", "disbursementamount"),
        )
        required = ("donor", "country_iso3", "year", "purpose_code")
        missing = [field for field in required if columns.get(field) is None]
        if missing:
            raise ValueError(
                f"OECD CRS file is missing required columns: {', '.join(missing)}"
            )
        for row in reader:
            stats["rows_read"] = int(stats["rows_read"]) + 1
            donor = str(row.get(columns["donor"]) or "").strip().upper()
            if not donor:
                stats["skipped_donor"] = int(stats["skipped_donor"]) + 1
                continue
            recipient = str(
                row.get(columns["country_iso3"]) or ""
            ).strip().upper()
            if not re.fullmatch(r"[A-Z]{3}", recipient):
                stats["skipped_aggregate_recipient"] = (
                    int(stats["skipped_aggregate_recipient"]) + 1
                )
                continue
            if selected is not None and recipient not in selected:
                stats["skipped_recipient_filter"] = (
                    int(stats["skipped_recipient_filter"]) + 1
                )
                continue
            year_text = str(row.get(columns["year"]) or "")
            match = re.search(r"(19|20)\d{2}", year_text)
            if not match:
                stats["skipped_year"] = int(stats["skipped_year"]) + 1
                continue
            year = int(match.group(0))
            title = " ".join(
                str(row.get(columns.get(field)) or "")
                for field in ("title", "description", "purpose_name")
                if columns.get(field)
            )
            sector, confidence = sector_from_purpose(
                str(row.get(columns["purpose_code"]) or ""),
                title,
            )
            if sector is None or confidence < 0.55:
                stats["skipped_sector"] = int(stats["skipped_sector"]) + 1
                continue
            key = (year, donor, recipient, sector)
            value = aggregates.setdefault(
                key,
                {
                    "donor_name": str(
                        row.get(columns.get("donor_name")) or donor
                    ).strip(),
                    "recipient_name": str(
                        row.get(columns.get("country_name")) or recipient
                    ).strip(),
                    "row_count": 0,
                    "commitment": 0.0,
                    "disbursement": 0.0,
                },
            )
            value["row_count"] = int(value["row_count"]) + 1
            value["commitment"] = float(value["commitment"]) + _number(
                row.get(columns.get("amount"))
            )
            value["disbursement"] = float(value["disbursement"]) + _number(
                row.get(columns.get("disbursement"))
            )
            stats["rows_aggregated"] = int(stats["rows_aggregated"]) + 1
    finally:
        handle.close()
        if archive is not None:
            archive.close()

    years = sorted({key[0] for key in aggregates})
    if not years:
        raise ValueError("No usable donor activity rows were found")
    placeholders = ",".join("?" for _ in years)
    imported_at = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            f"DELETE FROM donor_activity_aggregate WHERE reporting_year IN ({placeholders})",
            years,
        )
        conn.executemany(
            """INSERT INTO donor_activity_aggregate(
                   reporting_year, donor_code, donor_name, recipient_iso3,
                   recipient_name, sector_code, reporting_row_count,
                   commitment_usd_m, disbursement_usd_m, source_file,
                   source_url, imported_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                (
                    year,
                    donor,
                    value["donor_name"],
                    recipient,
                    value["recipient_name"],
                    sector,
                    value["row_count"],
                    value["commitment"],
                    value["disbursement"],
                    path.name,
                    source_url,
                    imported_at,
                )
                for (year, donor, recipient, sector), value in aggregates.items()
            ),
        )
    stats["aggregate_groups"] = len(aggregates)
    stats["years"] = years
    return stats


def _midrank_percentile(value: float, population: list[float]) -> float:
    if value <= 0 or not population:
        return 0.0
    less = sum(candidate < value for candidate in population)
    equal = sum(candidate == value for candidate in population)
    return 100.0 * (less + 0.5 * equal) / len(population)


def _unrestricted_midrank_percentile(
    value: float,
    population: list[float],
) -> float:
    if not population:
        return 0.0
    less = sum(candidate < value for candidate in population)
    equal = sum(candidate == value for candidate in population)
    return 100.0 * (less + 0.5 * equal) / len(population)


def _kendall_trend(values: list[float]) -> tuple[float, float]:
    """Return Mann-Kendall tau and tie-corrected normal p-value."""
    n = len(values)
    if n < 2:
        return 0.0, 1.0
    score = 0
    for left in range(n - 1):
        for right in range(left + 1, n):
            difference = values[right] - values[left]
            score += 1 if difference > 0 else -1 if difference < 0 else 0
    denominator = n * (n - 1) / 2
    tau = score / denominator if denominator else 0.0
    tie_term = sum(
        count * (count - 1) * (2 * count + 5)
        for count in Counter(values).values()
        if count > 1
    )
    variance = (n * (n - 1) * (2 * n + 5) - tie_term) / 18
    if variance <= 0:
        return tau, 1.0
    if score > 0:
        z_score = (score - 1) / math.sqrt(variance)
    elif score < 0:
        z_score = (score + 1) / math.sqrt(variance)
    else:
        z_score = 0.0
    return tau, math.erfc(abs(z_score) / math.sqrt(2))


def donor_supply_momentum_metrics(
    conn: sqlite3.Connection,
    *,
    snapshot_year: int,
    window_years: int = 6,
) -> tuple[dict[tuple[str, str], dict[str, object]], int]:
    """Estimate relative all-donor supply direction and volatility.

    Annual supply uses positive disbursements, falling back to commitments only
    when an entire country-sector-year has no positive disbursement. A linear
    slope on log1p(volume) limits the influence of a single very large project.
    Mann-Kendall tau is retained as a non-parametric direction diagnostic.
    """
    ensure_donor_supply_schema(conn)
    if window_years < 4:
        raise ValueError("window_years must be at least 4")
    max_year = conn.execute(
        "SELECT MAX(reporting_year) FROM donor_activity_aggregate"
    ).fetchone()[0]
    if max_year is None:
        return {}, snapshot_year
    cutoff = min(snapshot_year, int(max_year))
    first_year = cutoff - window_years + 1
    years = list(range(first_year, cutoff + 1))
    rows = conn.execute(
        """SELECT reporting_year, recipient_iso3, sector_code,
                  SUM(CASE WHEN disbursement_usd_m > 0
                           THEN disbursement_usd_m ELSE 0 END) disbursement,
                  SUM(CASE WHEN commitment_usd_m > 0
                           THEN commitment_usd_m ELSE 0 END) commitment
           FROM donor_activity_aggregate
           WHERE reporting_year BETWEEN ? AND ?
           GROUP BY reporting_year, recipient_iso3, sector_code""",
        (first_year, cutoff),
    ).fetchall()
    annual: dict[tuple[str, str, int], tuple[float, str]] = {}
    for row in rows:
        disbursement = float(row["disbursement"] or 0.0)
        commitment = float(row["commitment"] or 0.0)
        annual[
            (
                str(row["recipient_iso3"]),
                str(row["sector_code"]),
                int(row["reporting_year"]),
            )
        ] = (
            (disbursement, "disbursement")
            if disbursement > 0
            else (commitment, "commitment_fallback")
        )
    recipients = [
        str(row[0])
        for row in conn.execute(
            "SELECT DISTINCT recipient_iso3 FROM donor_activity_aggregate"
        )
    ]
    raw: dict[tuple[str, str], dict[str, object]] = {}
    for country in recipients:
        for sector in SECTORS:
            volumes: list[float] = []
            bases: list[str] = []
            for year in years:
                volume, basis = annual.get(
                    (country, sector, year),
                    (0.0, "no_activity"),
                )
                volumes.append(max(0.0, float(volume)))
                bases.append(basis)
            log_volumes = [math.log1p(value) for value in volumes]
            x_mean = statistics.fmean(years)
            y_mean = statistics.fmean(log_volumes)
            denominator = sum((year - x_mean) ** 2 for year in years)
            log_slope = (
                sum(
                    (year - x_mean) * (value - y_mean)
                    for year, value in zip(years, log_volumes)
                )
                / denominator
                if denominator
                else 0.0
            )
            fitted = [
                y_mean + log_slope * (year - x_mean) for year in years
            ]
            residual_rmse = math.sqrt(
                statistics.fmean(
                    (observed - predicted) ** 2
                    for observed, predicted in zip(log_volumes, fitted)
                )
            )
            tau, p_value = _kendall_trend(log_volumes)
            recent_log_change = (
                statistics.fmean(log_volumes[-2:])
                - statistics.fmean(log_volumes[-4:-2])
            )
            positive = [value for value in volumes if value > 0]
            coefficient_of_variation = (
                statistics.pstdev(volumes) / statistics.fmean(volumes)
                if statistics.fmean(volumes) > 0
                else 0.0
            )
            cagr_percent: float | None = None
            if volumes[0] > 0 and volumes[-1] > 0:
                cagr_percent = 100.0 * (
                    (volumes[-1] / volumes[0]) ** (1 / (window_years - 1))
                    - 1
                )
            if not positive:
                trend_direction = "no_activity"
            elif tau >= 0.6 and log_slope > 0:
                trend_direction = "sustained_growth"
            elif tau <= -0.6 and log_slope < 0:
                trend_direction = "sustained_decline"
            else:
                trend_direction = "mixed_or_flat"
            raw[(country, sector)] = {
                "first_year": first_year,
                "cutoff_year": cutoff,
                "years": years,
                "annual_volume_usd_m": volumes,
                "annual_volume_basis": bases,
                "active_year_count": len(positive),
                "log_volume_ols_slope": log_slope,
                "recent_two_year_log_change": recent_log_change,
                "mann_kendall_tau": tau,
                "mann_kendall_p_value": p_value,
                "log_residual_rmse": residual_rmse,
                "coefficient_of_variation": coefficient_of_variation,
                "cagr_percent": cagr_percent,
                "trend_direction": trend_direction,
            }

    slope_population = [
        float(value["log_volume_ols_slope"]) for value in raw.values()
    ]
    recent_population = [
        float(value["recent_two_year_log_change"]) for value in raw.values()
    ]
    for value in raw.values():
        if int(value["active_year_count"]) == 0:
            value["slope_percentile"] = 0.0
            value["recent_change_percentile"] = 0.0
            value["momentum_score"] = 0.0
            continue
        slope_percentile = _unrestricted_midrank_percentile(
            float(value["log_volume_ols_slope"]),
            slope_population,
        )
        recent_percentile = _unrestricted_midrank_percentile(
            float(value["recent_two_year_log_change"]),
            recent_population,
        )
        value["slope_percentile"] = slope_percentile
        value["recent_change_percentile"] = recent_percentile
        value["momentum_score"] = (
            0.70 * slope_percentile + 0.30 * recent_percentile
        )
    return raw, cutoff


def all_donor_supply_metrics(
    conn: sqlite3.Connection,
    *,
    snapshot_year: int,
    window_years: int = 3,
) -> tuple[dict[tuple[str, str], dict[str, float]], int]:
    """Calculate comparable all-donor supply, concentration and Korea share."""
    ensure_donor_supply_schema(conn)
    max_year = conn.execute(
        "SELECT MAX(reporting_year) FROM donor_activity_aggregate"
    ).fetchone()[0]
    if max_year is None:
        return {}, snapshot_year
    cutoff = min(snapshot_year, int(max_year))
    rows = conn.execute(
        """SELECT recipient_iso3, sector_code, donor_code,
                  SUM(CASE WHEN commitment_usd_m > 0
                           THEN commitment_usd_m ELSE 0 END) commitment,
                  SUM(CASE WHEN disbursement_usd_m > 0
                           THEN disbursement_usd_m ELSE 0 END) disbursement,
                  SUM(reporting_row_count) row_count
           FROM donor_activity_aggregate
           WHERE reporting_year BETWEEN ? AND ?
           GROUP BY recipient_iso3, sector_code, donor_code""",
        (cutoff - window_years + 1, cutoff),
    ).fetchall()
    donor_values: dict[tuple[str, str], list[dict[str, float | str]]] = defaultdict(list)
    for row in rows:
        donor_values[(row["recipient_iso3"], row["sector_code"])].append(
            {
                "donor": str(row["donor_code"]),
                "commitment": float(row["commitment"] or 0),
                "disbursement": float(row["disbursement"] or 0),
                "row_count": float(row["row_count"] or 0),
            }
        )
    country_values = {
        row[0] for row in conn.execute(
            "SELECT DISTINCT recipient_iso3 FROM donor_activity_aggregate"
        )
    }
    keys = [(country, sector) for country in country_values for sector in SECTORS]
    raw: dict[tuple[str, str], dict[str, float]] = {}
    for key in keys:
        donors = donor_values.get(key, [])
        total_disbursement = sum(float(item["disbursement"]) for item in donors)
        total_commitment = sum(float(item["commitment"]) for item in donors)
        use_disbursement = total_disbursement > 0
        volumes = {
            str(item["donor"]): float(
                item["disbursement"] if use_disbursement else item["commitment"]
            )
            for item in donors
            if float(
                item["disbursement"] if use_disbursement else item["commitment"]
            ) > 0
        }
        total_volume = sum(volumes.values())
        donor_count = len(volumes)
        shares = [
            volume / total_volume for volume in volumes.values()
        ] if total_volume > 0 else []
        hhi = sum(share * share for share in shares)
        korea_volume = sum(
            volume for donor, volume in volumes.items()
            if donor in {"KOR", "KOREA", "REPUBLIC OF KOREA"}
        )
        raw[key] = {
            "total_volume_usd_m": total_volume,
            "total_commitment_usd_m": total_commitment,
            "total_disbursement_usd_m": total_disbursement,
            "donor_count": float(donor_count),
            "hhi_0_1": hhi,
            "donor_diversity_0_100": (
                100.0 * (1.0 - hhi) if total_volume > 0 else 0.0
            ),
            "korea_volume_usd_m": korea_volume,
            "korea_share_0_100": (
                100.0 * korea_volume / total_volume if total_volume else 0.0
            ),
            "volume_basis": 1.0 if use_disbursement else 0.0,
        }
    volume_population = [
        value["total_volume_usd_m"] for value in raw.values()
    ]
    donor_population = [value["donor_count"] for value in raw.values()]
    for value in raw.values():
        volume_pct = _midrank_percentile(
            value["total_volume_usd_m"], volume_population
        )
        donor_pct = _midrank_percentile(
            value["donor_count"], donor_population
        )
        value["volume_percentile"] = volume_pct
        value["donor_count_percentile"] = donor_pct
        value["saturation_score"] = (
            0.60 * volume_pct
            + 0.25 * donor_pct
            + 0.15 * value["donor_diversity_0_100"]
        )
    return raw, cutoff
