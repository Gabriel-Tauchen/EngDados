import sys
import unittest
from pathlib import Path
import pandas as pd

# Add src and dashboard to python path
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
DASHBOARD_DIR = ROOT_DIR / "dashboard"

for p in (str(SRC_DIR), str(DASHBOARD_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import queries
from config import DB_PATH


class TestDashboardQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB_PATH.exists():
            raise unittest.SkipTest(f"DuckDB database not found at {DB_PATH}")

    def test_connection_read_only(self):
        """Verify the database connection is strictly read-only and forbids DDL mutations."""
        con = queries.get_connection(read_only=True)
        try:
            # Attempting write operations must raise an exception in read-only mode
            with self.assertRaises(Exception):
                con.execute("CREATE TABLE gold._test_mutation (id INT)")
        finally:
            con.close()

    def test_get_available_regions(self):
        regions = queries.get_available_regions()
        self.assertIsInstance(regions, list)
        self.assertIn("Europe", regions)

    def test_get_available_years(self):
        years = queries.get_available_years()
        self.assertIsInstance(years, list)
        self.assertIn(2022, years)
        self.assertIn(2019, years)
        # Verify years are descending
        self.assertEqual(years, sorted(years, reverse=True))

    def test_get_available_countries(self):
        all_countries = queries.get_available_countries()
        self.assertGreater(len(all_countries), 30)
        self.assertIn("France", all_countries)

        europe_countries = queries.get_available_countries(region="Europe")
        self.assertGreater(len(europe_countries), 20)
        self.assertIn("France", europe_countries)

    def test_get_indicators_by_region_and_year(self):
        df = queries.get_indicators_by_region_and_year(region="Europe", year=2022)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        expected_cols = {"country_name", "total_flights", "pct_change", "region_share_pct", "new_cases"}
        self.assertTrue(expected_cols.issubset(set(df.columns)))

    def test_get_flight_trend_by_country(self):
        df = queries.get_flight_trend_by_country("Germany")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertIn("year", df.columns)
        self.assertIn("total_flights", df.columns)
        years = df["year"].tolist()
        self.assertEqual(years, sorted(years))

    def test_get_top_airports(self):
        df = queries.get_top_airports(year=2022, limit=5)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 5)
        self.assertIn("airport_name", df.columns)
        self.assertIn("total_flights", df.columns)

    def test_get_summary_metrics(self):
        metrics = queries.get_summary_metrics(region="Europe", year=2022)
        self.assertIsInstance(metrics, dict)
        self.assertIn("total_flights", metrics)
        self.assertIn("total_new_cases", metrics)
        self.assertIn("avg_stringency", metrics)
        self.assertIn("country_count", metrics)
        self.assertGreater(metrics["total_flights"], 0)
        self.assertGreater(metrics["country_count"], 0)

    def test_sql_injection_safety(self):
        """Verify parameterized queries handle malicious injection strings harmlessly."""
        malicious_input = "'; DROP TABLE gold.fact_flights; --"
        df = queries.get_indicators_by_region_and_year(region=malicious_input, year=2022)
        self.assertTrue(df.empty)

    def test_get_multivariate_timeline_monthly(self):
        df = queries.get_multivariate_timeline("Germany", granularity="month", start_year=2020, end_year=2022)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        expected_cols = {"period", "total_flights", "new_cases", "avg_stringency"}
        self.assertTrue(expected_cols.issubset(set(df.columns)))
        # Verify 36 months for 3 years
        self.assertEqual(len(df), 36)

    def test_get_multivariate_timeline_yearly(self):
        df = queries.get_multivariate_timeline("Germany", granularity="year", start_year=2019, end_year=2024)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 6)

    def test_get_multivariate_timeline_all_countries(self):
        df = queries.get_multivariate_timeline("All Countries (Aggregated)", granularity="month", start_year=2020, end_year=2021)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 24)
        # Europe-wide volume should be substantially larger than individual countries
        self.assertGreater(df["total_flights"].sum(), 1_000_000)

    def test_get_flight_trend_all_countries(self):
        df = queries.get_flight_trend_by_country("All Countries (Aggregated)")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 6)
        self.assertGreater(df["total_flights"].sum(), 10_000_000)

    def test_normalize_series_min_max(self):
        data = pd.DataFrame({
            "period": ["2020-01", "2020-02", "2020-03"],
            "val1": [10.0, 20.0, 30.0],
            "val2": [100.0, 200.0, 300.0],
        })
        norm_df = queries.normalize_series_min_max(data, ["val1", "val2"])
        # Min becomes 0, Max becomes 100
        self.assertEqual(norm_df["val1"].min(), 0.0)
        self.assertEqual(norm_df["val1"].max(), 100.0)
        self.assertEqual(norm_df["val2"].min(), 0.0)
        self.assertEqual(norm_df["val2"].max(), 100.0)



if __name__ == "__main__":
    unittest.main()
