from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from urllib.parse import unquote

from opportunity_radar.db import connect, initialize
from opportunity_radar.mofa_pipeline import MOFA_SCHEMA
from opportunity_radar.opportunity_models import (
    MODEL_VERSION,
    NEED_INDICATORS,
    collect_world_bank_bulk_need_indicators,
    collect_world_bank_need_indicators,
    run_opportunity_models,
)
from opportunity_radar.project_history import _upsert_project


class _FakeResponse:
    def __init__(self, payload: object):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")


class OpportunityModelsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "models.db"
        self.conn = connect(self.db_path)
        initialize(self.conn)
        self.conn.executemany(
            """INSERT INTO country(iso3, iso2, name_ko, name_en, region_code)
               VALUES (?, ?, ?, ?, 'SEA')
               ON CONFLICT(iso3) DO UPDATE SET
                 iso2=excluded.iso2,
                 name_ko=excluded.name_ko,
                 name_en=excluded.name_en,
                 region_code=excluded.region_code""",
            (
                ("VNM", "VN", "베트남", "Vietnam"),
                ("IDN", "ID", "인도네시아", "Indonesia"),
                ("MNG", "MN", "몽골", "Mongolia"),
            ),
        )
        for index, (year, agency, amount) in enumerate(
            ((2022, "A", 10.0), (2023, "A", 20.0), (2024, "B", 30.0))
        ):
            _upsert_project(
                self.conn,
                source_type="OECD_CRS",
                source_project_id=f"VNM-{index}",
                country_iso3="VNM",
                sector_code="education",
                title=f"Vietnam education {index}",
                start_year=year,
                commitment_amount=amount,
                implementing_agency=agency,
            )
        _upsert_project(
            self.conn,
            source_type="OECD_CRS",
            source_project_id="IDN-1",
            country_iso3="IDN",
            sector_code="education",
            title="Indonesia education",
            start_year=2024,
            commitment_amount=5.0,
            implementing_agency="A",
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_collects_batched_need_indicators_with_conservative_spacing(self) -> None:
        values = {
            "SE.SEC.ENRR": {"VNM": 80.0, "IDN": 70.0, "MNG": 60.0},
            "SE.SEC.CMPT.LO.ZS": {"VNM": 75.0, "IDN": 65.0, "MNG": 55.0},
            "SE.PRM.CMPT.ZS": {"VNM": 90.0, "IDN": 80.0, "MNG": 70.0},
            "IT.NET.USER.ZS": {"VNM": 75.0, "IDN": 65.0, "MNG": 85.0},
            "IT.NET.BBND.P2": {"VNM": 20.0, "IDN": 15.0, "MNG": 25.0},
            "IT.CEL.SETS.P2": {"VNM": 130.0, "IDN": 120.0, "MNG": 140.0},
            "SH_UHC_SCI": {"VNM": 68.0, "IDN": 60.0, "MNG": 72.0},
            "SH.DYN.MORT": {"VNM": 18.0, "IDN": 22.0, "MNG": 15.0},
            "SH.STA.MMRT": {"VNM": 45.0, "IDN": 90.0, "MNG": 35.0},
        }
        requested: list[str] = []
        sleeps: list[float] = []

        def opener(request, **_kwargs):
            url = unquote(request.full_url)
            requested.append(url)
            indicator = next(code for code in values if f"/{code}?" in url)
            data = [
                {
                    "countryiso3code": country,
                    "date": "2024",
                    "value": value,
                }
                for country, value in values[indicator].items()
            ]
            return _FakeResponse([{"page": 1, "pages": 1}, data])

        result = collect_world_bank_need_indicators(
            self.conn,
            countries=("VNM", "IDN", "MNG"),
            end_year=2026,
            request_interval_seconds=1.25,
            opener=opener,
            sleeper=sleeps.append,
            validate_world_bank_countries=False,
        )

        self.assertEqual(result["requests"], 9)
        self.assertEqual(result["observations_upserted"], 27)
        self.assertEqual(sleeps, [1.25] * 8)
        self.assertTrue(
            all("/country/VNM;IDN;MNG/indicator/" in url for url in requested)
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM development_indicator_observation"
            ).fetchone()[0],
            27,
        )

    def test_collects_bulk_csv_zip_once_per_indicator(self) -> None:
        requested: list[str] = []
        sleeps: list[float] = []

        def make_zip(indicator_code: str) -> bytes:
            csv_buffer = io.StringIO(newline="")
            writer = csv.writer(csv_buffer)
            writer.writerow(["Data Source", "World Development Indicators"])
            writer.writerow([])
            writer.writerow(["Last Updated Date", "2026-01-01"])
            writer.writerow([])
            writer.writerow(
                [
                    "Country Name",
                    "Country Code",
                    "Indicator Name",
                    "Indicator Code",
                    "2014",
                    "2024",
                ]
            )
            for country, value in (
                ("VNM", 10.0),
                ("IDN", 20.0),
                ("MNG", 30.0),
                ("USA", 40.0),
            ):
                writer.writerow(
                    [
                        country,
                        country,
                        indicator_code,
                        indicator_code,
                        "999",
                        value,
                    ]
                )
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as archive:
                archive.writestr(
                    f"API_{indicator_code}_DS2_en_csv_v2_test.csv",
                    csv_buffer.getvalue(),
                )
                archive.writestr("Metadata_Country_API.csv", "metadata")
            return zip_buffer.getvalue()

        def opener(request, **_kwargs):
            requested.append(request.full_url)
            indicator = next(
                spec.indicator_code
                for spec in NEED_INDICATORS
                if spec.indicator_code in request.full_url
            )
            return _FakeResponse(make_zip(indicator))

        result = collect_world_bank_bulk_need_indicators(
            self.conn,
            countries=("VNM", "IDN", "MNG"),
            start_year=2015,
            end_year=2026,
            request_interval_seconds=1.25,
            opener=opener,
            sleeper=sleeps.append,
        )

        self.assertEqual(result["transport"], "bulk_csv_zip")
        self.assertEqual(result["requests"], 9)
        self.assertEqual(result["observations_upserted"], 27)
        self.assertEqual(sleeps, [1.25] * 8)
        self.assertTrue(
            all("downloadformat=csv" in url for url in requested)
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM development_indicator_observation"
            ).fetchone()[0],
            27,
        )

    def test_runs_separated_models_without_fabricating_total_score(self) -> None:
        education_values = {
            "VNM": {
                "SE.SEC.ENRR": 75.0,
                "SE.SEC.CMPT.LO.ZS": 80.0,
                "SE.PRM.CMPT.ZS": 90.0,
            },
            "IDN": {
                "SE.SEC.ENRR": 65.0,
                "SE.SEC.CMPT.LO.ZS": 70.0,
                "SE.PRM.CMPT.ZS": 80.0,
            },
            "MNG": {
                "SE.SEC.ENRR": 55.0,
                "SE.SEC.CMPT.LO.ZS": 50.0,
                "SE.PRM.CMPT.ZS": 60.0,
            },
        }
        self.conn.executemany(
            """INSERT INTO development_indicator_observation(
                   source_type, country_iso3, indicator_code, indicator_name,
                   observation_year, value, fetched_at, source_url
               ) VALUES ('WORLD_BANK_WDI', ?, ?, 'education', 2024, ?,
                         '2026-01-01T00:00:00Z',
                         'https://api.worldbank.org/test')""",
            [
                (country, indicator, value)
                for country, indicators in education_values.items()
                for indicator, value in indicators.items()
            ],
        )
        self.conn.executemany(
            """INSERT INTO donor_activity_aggregate(
                   reporting_year, donor_code, donor_name, recipient_iso3,
                   recipient_name, sector_code, reporting_row_count,
                   commitment_usd_m, disbursement_usd_m, source_file,
                   imported_at
               ) VALUES (2024, ?, ?, ?, ?, ?, 1, ?, ?, 'test.zip',
                         '2026-01-01T00:00:00Z')""",
            (
                ("USA", "United States", "VNM", "Vietnam", "education", 10.0, 10.0),
                ("JPN", "Japan", "IDN", "Indonesia", "education", 20.0, 20.0),
                ("KOR", "Korea", "MNG", "Mongolia", "health", 5.0, 5.0),
            ),
        )
        source_record = self.conn.execute(
            """INSERT INTO source_record(
                   source_type, external_id, country_iso3, title, published_at,
                   source_url
               ) VALUES (
                   'LOD', 'POLICY-VNM-EDU', 'VNM',
                   '베트남 교육 협력 양해각서', '2025-01-01',
                   'https://example.test/policy'
               )"""
        )
        self.conn.execute(
            """INSERT INTO evidence(
                   source_record_id, country_iso3, sector_code, event_type,
                   event_date, organizations_json, confidence, supporting_text
               ) VALUES (
                   ?, 'VNM', 'education', 'mou', '2025-01-01',
                   '["MOFA", "MOET"]', 0.9,
                   '한국과 베트남은 교육 협력 양해각서를 체결했다.'
               )""",
            (source_record.lastrowid,),
        )
        self.conn.executescript(MOFA_SCHEMA)
        self.conn.executemany(
            """INSERT INTO country_profile(
                   country_iso3, profile_type, observed_at,
                   gdp_growth_rate, inflation_rate, data_json
               ) VALUES (?, 'economy', '2026-01-01', 5.0, 3.0, '{}')""",
            (("VNM",), ("IDN",), ("MNG",)),
        )
        self.conn.executemany(
            """INSERT INTO safety_notice(
                   external_id, country_iso3, warning_level, published_at,
                   title, source_url
               ) VALUES (?, ?, ?, '2026-01-01', ?, 'https://example.test/risk')""",
            (
                ("RISK-VNM", "VNM", 1, "Vietnam caution"),
                ("RISK-IDN", "IDN", 3, "Indonesia review"),
                ("RISK-MNG", "MNG", 4, "Mongolia blocked"),
            ),
        )
        self.conn.executemany(
            """INSERT INTO source_coverage(
                   country_iso3, source_type, observed_at, record_count
               ) VALUES (?, ?, '2026-01-01', 1)""",
            [
                (country, source)
                for country in ("VNM", "IDN", "MNG")
                for source in ("KOICA", "MOFA")
            ],
        )
        self.conn.commit()

        result = run_opportunity_models(
            self.conn,
            countries=("VNM", "IDN", "MNG"),
            snapshot_year=2026,
        )

        self.assertEqual(len(result["profiles"]), 24)
        self.assertNotIn("opportunity_score", result["profiles"][0])
        mongolia_education = next(
            row for row in result["profiles"]
            if row["country_iso3"] == "MNG"
            and row["sector_code"] == "education"
        )
        self.assertEqual(
            mongolia_education["candidate_type"], "potential_whitespace"
        )
        self.assertEqual(mongolia_education["all_donor_saturation"], 0.0)
        self.assertIsNotNone(mongolia_education["all_donor_momentum"])
        self.assertEqual(
            mongolia_education["implementation_status"],
            "blocked_by_safety",
        )
        vietnam_education = next(
            row
            for row in result["profiles"]
            if row["country_iso3"] == "VNM"
            and row["sector_code"] == "education"
        )
        self.assertEqual(
            vietnam_education["implementation_status"],
            "screen_ready",
        )
        indonesia_education = next(
            row
            for row in result["profiles"]
            if row["country_iso3"] == "IDN"
            and row["sector_code"] == "education"
        )
        self.assertEqual(
            indonesia_education["implementation_status"],
            "manual_risk_review",
        )
        mongolia_need_components = json.loads(
            self.conn.execute(
                """SELECT components_json
                   FROM opportunity_model_score
                   WHERE country_iso3='MNG' AND sector_code='education'
                     AND snapshot_year=2026 AND model_code='unmet_need'
                     AND model_version=?""",
                (MODEL_VERSION,),
            ).fetchone()[0]
        )
        sensitivity = mongolia_need_components["sensitivity"]
        self.assertEqual(len(sensitivity["scores"]), 3)
        self.assertTrue(sensitivity["threshold_classification_stable"])
        self.assertGreaterEqual(sensitivity["range"], 0.0)
        vnm_supply = self.conn.execute(
            """SELECT score, evidence_status, components_json
               FROM opportunity_model_score
               WHERE country_iso3='VNM' AND sector_code='education'
                 AND snapshot_year=2026 AND model_code='korean_supply_intensity'
                 AND model_version=?""",
            (MODEL_VERSION,),
        ).fetchone()
        idn_supply = self.conn.execute(
            """SELECT score FROM opportunity_model_score
               WHERE country_iso3='IDN' AND sector_code='education'
                 AND snapshot_year=2026 AND model_code='korean_supply_intensity'
                 AND model_version=?""",
            (MODEL_VERSION,),
        ).fetchone()
        self.assertGreater(vnm_supply["score"], idn_supply["score"])
        self.assertEqual(vnm_supply["evidence_status"], "descriptive_only")
        vnm_policy = self.conn.execute(
            """SELECT score, evidence_status, components_json
               FROM opportunity_model_score
               WHERE country_iso3='VNM' AND sector_code='education'
                 AND snapshot_year=2026 AND model_code='policy_fit'
                 AND model_version=?""",
            (MODEL_VERSION,),
        ).fetchone()
        self.assertIsNotNone(vnm_policy["score"])
        self.assertEqual(
            vnm_policy["evidence_status"],
            "rule_based_evidence",
        )
        self.assertEqual(
            json.loads(vnm_policy["components_json"])[
                "approved_tier_ab_count"
            ],
            1,
        )
        self.assertIn(
            "not market saturation",
            json.loads(
                self.conn.execute(
                    """SELECT caveats_json FROM opportunity_model_score
                       WHERE country_iso3='VNM' AND sector_code='education'
                         AND snapshot_year=2026
                         AND model_code='korean_supply_intensity'
                         AND model_version=?""",
                    (MODEL_VERSION,),
                ).fetchone()[0]
            )[0],
        )
        digital_need = self.conn.execute(
            """SELECT score, evidence_status FROM opportunity_model_score
               WHERE country_iso3='VNM' AND sector_code='digital'
                 AND snapshot_year=2026 AND model_code='unmet_need'
                 AND model_version=?""",
            (MODEL_VERSION,),
        ).fetchone()
        self.assertIsNone(digital_need["score"])
        self.assertEqual(digital_need["evidence_status"], "insufficient_data")


if __name__ == "__main__":
    unittest.main()
