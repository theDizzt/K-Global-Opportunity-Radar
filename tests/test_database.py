import tempfile
import unittest
from pathlib import Path

from backend.database.connection import get_connection
from backend.database.init_db import initialize_database
from backend.repositories.analysis_repository import AnalysisRepository
from backend.repositories.country_repository import CountryRepository


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "test.db"
        initialize_database(self.database_path, reset=True)

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_schema_and_seed_counts(self):
        with get_connection(self.database_path) as connection:
            counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "countries",
                    "country_indicators",
                    "signal_history",
                    "evidence",
                    "recommendations",
                    "risk_factors",
                    "data_sources",
                    "collection_logs",
                )
            }

        self.assertEqual(counts["countries"], 3)
        self.assertEqual(counts["country_indicators"], 15)
        self.assertEqual(counts["signal_history"], 15)
        self.assertEqual(counts["evidence"], 9)
        self.assertEqual(counts["recommendations"], 9)
        self.assertEqual(counts["risk_factors"], 6)
        self.assertEqual(counts["data_sources"], 4)
        self.assertEqual(counts["collection_logs"], 4)

    def test_initialization_is_idempotent(self):
        initialize_database(self.database_path)
        repository = CountryRepository(self.database_path)
        self.assertEqual(repository.count(), 3)

    def test_repositories_read_normalized_data(self):
        countries = CountryRepository(self.database_path)
        analysis = AnalysisRepository(self.database_path)

        vietnam = countries.get_by_iso3("vnm")
        self.assertEqual(vietnam.country, "베트남")
        self.assertEqual(vietnam.diplomacy, 89)
        self.assertEqual(len(analysis.get_signal_history("VNM")), 5)
        self.assertEqual(len(analysis.get_evidence("VNM")), 3)
        self.assertEqual(len(analysis.get_recommendations("VNM")), 3)
        self.assertEqual(len(analysis.get_risks("VNM")), 2)


if __name__ == "__main__":
    unittest.main()
