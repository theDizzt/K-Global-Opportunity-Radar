from __future__ import annotations

import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.project_history import load_activity_file
from opportunity_radar.statistical_signals import (
    build_signal_panel,
    ensure_signal_schema,
    predict_current_candidates,
    validate_signals,
)


class StatisticalSignalsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = connect(Path(self.tmp.name) / "signals.db")
        initialize(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _project(self, uid: str, country: str, sector: str, year: int) -> None:
        self.conn.execute(
            """INSERT INTO project_master(
                   project_uid, source_type, source_project_id, country_iso3,
                   sector_code, title, start_year, is_new
               ) VALUES (?, 'TEST', ?, ?, ?, ?, ?, 1)""",
            (uid, uid, country, sector, uid, year),
        )

    def _signal(self, evidence_id: int, country: str, sector: str, year: int) -> None:
        record = self.conn.execute(
            """INSERT INTO source_record(
                   source_type, external_id, country_iso3, title, published_at
               ) VALUES ('LOD', ?, ?, 'cooperation signal', ?)""",
            (f"LOD-{evidence_id}", country, f"{year}-01-01"),
        )
        self.conn.execute(
            """INSERT INTO evidence(
                   source_record_id, country_iso3, sector_code, event_type,
                   event_date, confidence, supporting_text
               ) VALUES (?, ?, ?, 'press_mention', ?, 0.9, 'cooperation')""",
            (record.lastrowid, country, sector, f"{year}-01-01"),
        )

    def test_panel_uses_only_past_features_and_future_outcome(self):
        ensure_signal_schema(self.conn)
        self._signal(1, "VNM", "digital", 2010)
        self._project("P-2012", "VNM", "digital", 2012)
        self.conn.commit()

        result = build_signal_panel(
            self.conn,
            horizon_years=2,
            start_year=2010,
            outcome_cutoff_year=2014,
            countries=["VNM"],
            sectors=["digital"],
        )

        self.assertEqual(result["rows"], 3)
        row_2010 = self.conn.execute(
            """SELECT * FROM cooperation_signal_panel
               WHERE country_iso3='VNM' AND sector_code='digital'
                 AND snapshot_year=2010 AND horizon_years=2"""
        ).fetchone()
        row_2012 = self.conn.execute(
            """SELECT * FROM cooperation_signal_panel
               WHERE country_iso3='VNM' AND sector_code='digital'
                 AND snapshot_year=2012 AND horizon_years=2"""
        ).fetchone()
        self.assertEqual(row_2010["outcome_new_project"], 1)
        self.assertEqual(row_2010["prior_project_count_3y"], 0)
        self.assertEqual(row_2012["outcome_new_project"], 0)
        self.assertEqual(row_2012["prior_project_count_3y"], 1)

    def test_chronological_validation_records_baseline_comparison(self):
        ensure_signal_schema(self.conn)
        for year in range(2000, 2024):
            for country_index, country in enumerate(("VNM", "IDN", "MNG")):
                for sector_index, sector in enumerate(("education", "digital")):
                    signal = int((year + country_index + sector_index) % 3 == 0)
                    outcome = signal
                    self.conn.execute(
                        """INSERT INTO cooperation_signal_panel(
                               country_iso3, sector_code, snapshot_year, horizon_years,
                               signal_count_1y, signal_count_3y, signal_weight_3y,
                               signal_trend, tier_ab_count_3y, source_diversity_3y,
                               partner_diversity_3y, prior_project_count_3y,
                               prior_project_count_5y, years_since_last_project,
                               data_coverage, outcome_new_project, outcome_project_count,
                               outcome_commitment
                           ) VALUES (?, ?, ?, 2, ?, ?, ?, ?, 0, 1, 0, 0, 0, 10, 0.67, ?, ?, 0)""",
                        (
                            country,
                            sector,
                            year,
                            signal,
                            signal,
                            float(signal),
                            float(signal),
                            outcome,
                            outcome,
                        ),
                    )
        self.conn.commit()

        result = validate_signals(self.conn, horizon_years=2, test_start_year=2018)

        self.assertEqual(result["status"], "validated")
        self.assertGreater(result["metrics"]["lift_top_10pct"], 1)
        self.assertIn("structural_brier", result["metrics"])
        self.assertGreater(
            result["metrics"]["signal_brier_improvement_vs_structural"],
            0,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM signal_validation_run").fetchone()[0],
            1,
        )
        self.assertGreater(
            len(predict_current_candidates(self.conn, horizon_years=2, snapshot_year=2024)),
            0,
        )

    def test_imports_korean_oda_activity_csv(self):
        path = Path(self.tmp.name) / "activities.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "Donor",
                    "Recipient ISO3",
                    "CRS ID",
                    "Project title",
                    "Purpose code",
                    "Expected start date",
                    "USD commitment",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "Donor": "KOR",
                    "Recipient ISO3": "VNM",
                    "CRS ID": "CRS-1",
                    "Project title": "Digital education capacity",
                    "Purpose code": "11110",
                    "Expected start date": "2021-01-01",
                    "USD commitment": "1000000",
                }
            )

        result = load_activity_file(self.conn, path)

        self.assertEqual(result["loaded"], 1)
        row = self.conn.execute(
            "SELECT source_type, country_iso3, sector_code, start_year FROM project_master"
        ).fetchone()
        self.assertEqual(tuple(row), ("OECD_CRS", "VNM", "education", 2021))

    def test_imports_official_pipe_text_inside_zip(self):
        path = Path(self.tmp.name) / "crs.zip"
        header = (
            '"Year"|"DEDonorcode"|"DonorName"|"CrsID"|"RecipientCode"|'
            '"RecipientName"|"ProjectTitle"|"PurposeCode"|"ExpectedStartDate"|'
            '"USD_Commitment"|"AgencyName"\n'
        )
        rows = (
            '2024|KOR|Korea|KOR-1|769|Viet Nam|Teacher training|11110|2024-01-01|25|KOICA\n'
            '2024|USA|United States|USA-1|769|Viet Nam|Health|12220|2024-01-01|50|USAID\n'
        )
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("CRS 2024 data.txt", header + rows)

        result = load_activity_file(
            self.conn,
            path,
            country_map_path=Path(__file__).parents[1] / "docs" / "oecd_country_mapping.csv",
        )

        self.assertEqual(result["loaded"], 1)
        self.assertEqual(result["skipped_donor"], 1)
        row = self.conn.execute(
            "SELECT source_project_id, implementing_agency FROM project_master"
        ).fetchone()
        self.assertEqual(tuple(row), ("KOR-1", "KOICA"))


if __name__ == "__main__":
    unittest.main()
