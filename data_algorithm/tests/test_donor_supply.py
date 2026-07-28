from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from opportunity_radar.db import connect, initialize
from opportunity_radar.donor_supply import (
    all_donor_supply_metrics,
    donor_supply_momentum_metrics,
    load_all_donor_crs_file,
)


class DonorSupplyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = connect(Path(self.temp_dir.name) / "donors.db")
        initialize(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def _archive(self) -> Path:
        path = Path(self.temp_dir.name) / "CRS 2024 data.zip"
        header = (
            '"Year"|"DEDonorcode"|"DonorName"|"DERecipientcode"|'
            '"RecipientName"|"ProjectTitle"|"PurposeCode"|'
            '"USD_Commitment"|"USD_Disbursement"\n'
        )
        rows = (
            "2024|KOR|Korea|VNM|Viet Nam|Teacher training|11110|10|8\n"
            "2024|USA|United States|VNM|Viet Nam|School support|11110|30|12\n"
            "2024|JPN|Japan|VNM|Viet Nam|Health system|12220|5|4\n"
            "2024|USA|United States|IDN|Indonesia|School support|11110|100|100\n"
            "2024|AUS|Australia|MNG|Mongolia|Connectivity|220|20|15\n"
            "2024|USA|United States|DPGC_X|Aggregate|Other|998|50|50\n"
        )
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("CRS 2024 data.txt", header + rows)
        return path

    def test_import_is_idempotent_and_preserves_donor_dimension(self) -> None:
        path = self._archive()

        first = load_all_donor_crs_file(self.conn, path)
        count_after_first = self.conn.execute(
            "SELECT COUNT(*) FROM donor_activity_aggregate"
        ).fetchone()[0]
        second = load_all_donor_crs_file(self.conn, path)
        count_after_second = self.conn.execute(
            "SELECT COUNT(*) FROM donor_activity_aggregate"
        ).fetchone()[0]

        self.assertEqual(first["rows_aggregated"], 5)
        self.assertEqual(first["skipped_aggregate_recipient"], 1)
        self.assertEqual(count_after_first, 5)
        self.assertEqual(count_after_second, count_after_first)
        self.assertEqual(second["aggregate_groups"], 5)
        digital = self.conn.execute(
            """SELECT sector_code, disbursement_usd_m
               FROM donor_activity_aggregate
               WHERE donor_code='AUS' AND recipient_iso3='MNG'"""
        ).fetchone()
        self.assertEqual(tuple(digital), ("digital", 15.0))

    def test_calculates_hhi_korea_share_and_relative_saturation(self) -> None:
        load_all_donor_crs_file(self.conn, self._archive())

        metrics, cutoff = all_donor_supply_metrics(
            self.conn, snapshot_year=2026
        )
        vietnam = metrics[("VNM", "education")]
        indonesia = metrics[("IDN", "education")]

        self.assertEqual(cutoff, 2024)
        self.assertAlmostEqual(vietnam["total_volume_usd_m"], 20.0)
        self.assertAlmostEqual(vietnam["korea_share_0_100"], 40.0)
        self.assertAlmostEqual(vietnam["hhi_0_1"], 0.52)
        self.assertEqual(vietnam["donor_count"], 2.0)
        self.assertEqual(metrics[("VNM", "korean_studies")]["saturation_score"], 0.0)
        self.assertGreater(
            indonesia["volume_percentile"], vietnam["volume_percentile"]
        )
        self.assertGreater(
            vietnam["saturation_score"], indonesia["saturation_score"]
        )

    def test_estimates_growth_decline_and_flat_supply_momentum(self) -> None:
        rows = []
        patterns = {
            "VNM": [1, 2, 4, 8, 16, 32],
            "IDN": [32, 16, 8, 4, 2, 1],
            "MNG": [5, 5, 5, 5, 5, 5],
        }
        for country, volumes in patterns.items():
            for year, volume in zip(range(2019, 2025), volumes):
                rows.append(
                    (
                        year,
                        "USA",
                        "United States",
                        country,
                        country,
                        "education",
                        1,
                        volume,
                        volume,
                        f"CRS {year}.zip",
                        "2026-01-01T00:00:00Z",
                    )
                )
        self.conn.executemany(
            """INSERT INTO donor_activity_aggregate(
                   reporting_year, donor_code, donor_name, recipient_iso3,
                   recipient_name, sector_code, reporting_row_count,
                   commitment_usd_m, disbursement_usd_m, source_file,
                   imported_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self.conn.commit()

        metrics, cutoff = donor_supply_momentum_metrics(
            self.conn,
            snapshot_year=2026,
        )
        growing = metrics[("VNM", "education")]
        declining = metrics[("IDN", "education")]
        flat = metrics[("MNG", "education")]

        self.assertEqual(cutoff, 2024)
        self.assertEqual(growing["trend_direction"], "sustained_growth")
        self.assertEqual(declining["trend_direction"], "sustained_decline")
        self.assertEqual(flat["trend_direction"], "mixed_or_flat")
        self.assertGreater(
            growing["log_volume_ols_slope"],
            flat["log_volume_ols_slope"],
        )
        self.assertGreater(
            growing["momentum_score"],
            declining["momentum_score"],
        )
        self.assertAlmostEqual(flat["coefficient_of_variation"], 0.0)


if __name__ == "__main__":
    unittest.main()
