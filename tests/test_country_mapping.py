import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from country_mapping import COUNTRY_MAP, resolve_canonical_country


class TestCountryMapping(unittest.TestCase):
    def test_known_canonical_mappings(self):
        cases = {
            "turkey": "Turkey",
            "turkiye": "Turkey",
            "czech republic": "Czechia",
            "czechia": "Czechia",
            "uk": "United Kingdom",
            "united kingdom": "United Kingdom",
            "bosnia & herzegovina": "Bosnia and Herzegovina",
            "republic of moldova": "Moldova",
            "republic of north macedonia": "North Macedonia",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(resolve_canonical_country(raw), expected)

    def test_eurocontrol_partner_states(self):
        partners = ["Armenia", "Georgia", "Israel", "Morocco", "Turkey"]
        for country in partners:
            with self.subTest(country=country):
                self.assertEqual(resolve_canonical_country(country), country)

    def test_accents_and_whitespace(self):
        self.assertEqual(resolve_canonical_country("  España  "), "Spain")
        self.assertEqual(resolve_canonical_country("\tGERMANY\n"), "Germany")

    def test_invalid_and_unknown_inputs(self):
        self.assertIsNone(resolve_canonical_country(None))
        self.assertIsNone(resolve_canonical_country(""))
        self.assertEqual(resolve_canonical_country("Atlantis"), "Atlantis")


if __name__ == "__main__":
    unittest.main()
