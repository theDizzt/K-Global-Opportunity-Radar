import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from opportunity_radar.backend_sync import sync_backend


class BackendSyncTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.algorithm_path = root / "algorithm.db"
        self.backend_path = root / "backend.db"
        self._create_algorithm_database()
        self._create_backend_database()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_syncs_scores_and_evidence_idempotently(self):
        first = sync_backend(self.algorithm_path, self.backend_path, is_demo=True)
        second = sync_backend(self.algorithm_path, self.backend_path, is_demo=True)

        self.assertEqual(first.scores, 1)
        self.assertEqual(first.documents, 1)
        self.assertEqual(second.scores, 1)
        self.assertEqual(second.documents, 1)

        with closing(sqlite3.connect(self.backend_path)) as connection:
            score = connection.execute(
                """
                SELECT field, demand_score, policy_alignment_score,
                       readiness_score, korean_base_score, data_confidence, is_demo
                FROM opportunity_scores
                """
            ).fetchone()
            document = connection.execute(
                """
                SELECT d.source_code, d.primary_field, dc.country_iso3
                FROM source_documents AS d
                JOIN document_countries AS dc USING(document_uri)
                """
            ).fetchone()
            self.assertEqual(
                score,
                ("교육", 80.0, 70.0, 60.0, 50.0, 90.0, 1),
            )
            self.assertEqual(document, ("KOICA", "교육", "VNM"))
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM opportunity_scores").fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0],
                1,
            )

    def _create_algorithm_database(self):
        with closing(sqlite3.connect(self.algorithm_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE score_snapshot (
                    country_iso3 TEXT, sector_code TEXT, score_version TEXT,
                    as_of_date TEXT, demand_score REAL, alignment_score REAL,
                    readiness_score REAL, korea_base_score REAL,
                    opportunity_score REAL, data_confidence REAL,
                    risk_level INTEGER, sensitivity_low REAL,
                    sensitivity_high REAL
                );
                CREATE TABLE source_record (
                    id INTEGER PRIMARY KEY, source_type TEXT, external_id TEXT,
                    country_iso3 TEXT, title TEXT, body TEXT,
                    published_at TEXT, source_url TEXT
                );
                CREATE TABLE record_sector (
                    source_record_id INTEGER, sector_code TEXT,
                    confidence REAL, is_primary INTEGER, mapping_method TEXT
                );
                INSERT INTO score_snapshot VALUES (
                    'VNM', 'education', 'v-test', '2026-07-23',
                    80, 70, 60, 50, 68, 90, 1, 65, 71
                );
                INSERT INTO source_record VALUES (
                    1, 'KOICA', 'project-1', 'VNM', '교육 협력사업',
                    '교원 역량강화 사업', '2026-07-01',
                    'https://example.test/koica/project-1'
                );
                INSERT INTO record_sector VALUES (
                    1, 'education', 0.95, 1, 'test'
                );
                """
            )

    def _create_backend_database(self):
        with closing(sqlite3.connect(self.backend_path)) as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE countries (iso3 TEXT PRIMARY KEY);
                CREATE TABLE data_sources (code TEXT PRIMARY KEY);
                CREATE TABLE opportunity_scores (
                    country_iso3 TEXT, field TEXT, score_version TEXT,
                    as_of_date TEXT, demand_score REAL,
                    policy_alignment_score REAL, readiness_score REAL,
                    korean_base_score REAL, opportunity_score REAL,
                    data_confidence REAL, is_demo INTEGER DEFAULT 0, risk_level INTEGER,
                    sensitivity_low REAL, sensitivity_high REAL,
                    PRIMARY KEY(country_iso3, field, score_version, as_of_date)
                );
                CREATE TABLE source_documents (
                    document_uri TEXT PRIMARY KEY, source_code TEXT,
                    dataset_code TEXT, title TEXT, summary TEXT,
                    published_date TEXT, source_url TEXT, primary_field TEXT,
                    collected_at TEXT, raw_payload_id INTEGER
                );
                CREATE TABLE document_countries (
                    document_uri TEXT, country_iso3 TEXT,
                    PRIMARY KEY(document_uri, country_iso3)
                );
                INSERT INTO countries VALUES ('VNM');
                INSERT INTO data_sources VALUES ('KOICA');
                """
            )


if __name__ == "__main__":
    unittest.main()
