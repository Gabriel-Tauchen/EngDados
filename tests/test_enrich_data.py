import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from enrich_data import derive_post_merge_attributes, merge_datasets


class TestEnrichData(unittest.TestCase):
    def setUp(self):
        self.flights = pd.DataFrame({
            "country_name": ["France", "France", "Germany"],
            "FLT_DATE": pd.to_datetime(["2020-05-01", "2020-05-02", "2020-05-01"]),
            "TOTAL_FLIGHTS": [100, 200, 50],
        })
        self.covid = pd.DataFrame({
            "country_name": ["France", "France", "Germany"],
            "date": pd.to_datetime(["2020-05-01", "2020-05-02", "2020-05-01"]),
            "iso_code": ["FRA", "FRA", "DEU"],
            "new_cases": [500, 1000, 200],
            "total_cases": [10000, 11000, 5000],
            "new_cases_per_million": [10.0, 20.0, 5.0],
            "total_cases_per_million": [200.0, 220.0, 100.0],
            "new_deaths": [20, 30, 10],
            "total_deaths": [500, 530, 200],
            "new_deaths_per_million": [0.4, 0.6, 0.2],
            "stringency_index": [80.0, 80.0, 75.0],
            "population": [67_000_000, 67_000_000, 83_000_000],
        })

    def test_merge_datasets_many_to_one(self):
        merged = merge_datasets(self.flights, self.covid)
        self.assertEqual(len(merged), len(self.flights))
        self.assertIn("stringency_index", merged.columns)
        self.assertEqual(merged["iso_code"].tolist(), ["FRA", "FRA", "DEU"])

    def test_derive_post_merge_attributes(self):
        merged = merge_datasets(self.flights, self.covid)
        enriched = derive_post_merge_attributes(merged)
        self.assertIn("flights_per_million_pop", enriched.columns)
        self.assertIn("flights_to_cases_ratio", enriched.columns)

        # Flights per million pop for France on day 1: 100 / 67 = ~1.4925
        expected_ratio = 100 / (67_000_000 / 1_000_000)
        self.assertAlmostEqual(enriched["flights_per_million_pop"].iloc[0], expected_ratio, places=3)
        self.assertFalse(np.isinf(enriched["flights_per_million_pop"]).any())


if __name__ == "__main__":
    unittest.main()
