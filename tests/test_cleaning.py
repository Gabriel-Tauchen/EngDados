import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cleaning import (
    calculate_percentage_change,
    categorize_by_quartile,
    create_text_key,
    format_date_column,
    strip_whitespace,
)


class TestCleaning(unittest.TestCase):
    def test_strip_whitespace(self):
        df = pd.DataFrame({
            " col_a ": ["  val1 ", "val2  ", None],
            "col_b": [10, 20, 30],
        })
        cleaned = strip_whitespace(df)
        self.assertEqual(list(cleaned.columns), ["col_a", "col_b"])
        self.assertEqual(cleaned["col_a"].iloc[0], "val1")
        self.assertEqual(cleaned["col_a"].iloc[1], "val2")
        self.assertTrue(pd.isna(cleaned["col_a"].iloc[2]))
        self.assertEqual(cleaned["col_b"].tolist(), [10, 20, 30])

    def test_create_text_key(self):
        s = pd.Series(["  Françe  ", "TURKEY ", "São Tomé", ""])
        keys = create_text_key(s)
        self.assertEqual(keys.iloc[0], "france")
        self.assertEqual(keys.iloc[1], "turkey")
        self.assertEqual(keys.iloc[2], "sao tome")
        self.assertEqual(keys.iloc[3], "")

    def test_format_date_column(self):
        df = pd.DataFrame({"date_str": ["2020-01-01", "2020-01-02", "invalid_date"]})
        formatted = format_date_column(df, "date_str", "%Y-%m-%d")
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(formatted["date_str"]))
        self.assertEqual(formatted["date_str"].iloc[0], pd.Timestamp("2020-01-01"))
        self.assertTrue(pd.isna(formatted["date_str"].iloc[2]))

    def test_calculate_percentage_change_normal(self):
        df = pd.DataFrame({
            "group": ["A", "A", "A"],
            "date": ["2020-01-01", "2020-01-02", "2020-01-03"],
            "value": [100, 150, 120],
        })
        res = calculate_percentage_change(df, "group", "date", "value", "pct")
        self.assertAlmostEqual(res["pct"].iloc[0], 0.0)
        self.assertAlmostEqual(res["pct"].iloc[1], 50.0)
        self.assertAlmostEqual(res["pct"].iloc[2], -20.0)

    def test_calculate_percentage_change_safe_inf(self):
        """Verify that transitioning from 0 to a positive value does not produce inf."""
        df = pd.DataFrame({
            "group": ["A", "A", "B", "B"],
            "date": ["2020-01-01", "2020-01-02", "2020-01-01", "2020-01-02"],
            "value": [0, 50, 0, 0],
        })
        res = calculate_percentage_change(df, "group", "date", "value", "pct")
        self.assertFalse(np.isinf(res["pct"]).any(), "Percentage change produced inf!")
        self.assertEqual(res["pct"].iloc[1], 0.0)

    def test_categorize_by_quartile(self):
        df = pd.DataFrame({"val": range(1, 101)})
        res = categorize_by_quartile(df, "val", "quartile", ["Q1", "Q2", "Q3", "Q4"])
        self.assertEqual(list(res["quartile"].cat.categories), ["Q1", "Q2", "Q3", "Q4"])
        self.assertEqual(len(res["quartile"]), 100)


if __name__ == "__main__":
    unittest.main()
