import sys
import unittest
from pathlib import Path
import duckdb

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import load_data
from config import DB_PATH, GOLD_DIR, SILVER_COVID, SILVER_ENRICHED, SILVER_FLIGHT


class TestLoadDataDuckDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use isolated in-memory DuckDB for fast and non-destructive unit testing
        cls.con = duckdb.connect(":memory:")
        load_data.create_schemas(cls.con)
        load_data.load_silver_tables(cls.con)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def test_schemas_created(self):
        schemas = [row[0] for row in self.con.execute("SELECT schema_name FROM information_schema.schemata").fetchall()]
        self.assertIn("silver", schemas)
        self.assertIn("gold", schemas)

    def test_silver_tables_loaded(self):
        count_air = load_data.fetch_scalar(self.con, "SELECT COUNT(*) FROM silver.air_traffic_eu")
        count_covid = load_data.fetch_scalar(self.con, "SELECT COUNT(*) FROM silver.covid19")
        count_enriched = load_data.fetch_scalar(self.con, "SELECT COUNT(*) FROM silver.flights_covid_enriched")

        self.assertGreater(count_air, 0)
        self.assertGreater(count_covid, 0)
        self.assertGreater(count_enriched, 0)

    def test_silver_table_columns(self):
        columns = [row[0] for row in self.con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'silver' AND table_name = 'air_traffic_eu'"
        ).fetchall()]
        for expected_col in ("APT_ICAO", "APT_NAME", "FLT_DATE", "TOTAL_FLIGHTS"):
            self.assertIn(expected_col, columns)


if __name__ == "__main__":
    unittest.main()
