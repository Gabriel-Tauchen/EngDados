"""Canonical country mapping between Eurocontrol and Our World in Data."""

import unicodedata

COUNTRY_MAP = {
    "albania": "Albania",
    "andorra": "Andorra",
    "armenia": "Armenia",
    "austria": "Austria",
    "belarus": "Belarus",
    "belgium": "Belgium",
    "bosnia and herzegovina": "Bosnia and Herzegovina",
    "bosnia & herzegovina": "Bosnia and Herzegovina",
    "bulgaria": "Bulgaria",
    "croatia": "Croatia",
    "cyprus": "Cyprus",
    "czech republic": "Czechia",
    "czechia": "Czechia",
    "denmark": "Denmark",
    "england": "England",
    "estonia": "Estonia",
    "faeroe islands": "Faroe Islands",
    "faroe islands": "Faroe Islands",
    "finland": "Finland",
    "france": "France",
    "georgia": "Georgia",
    "germany": "Germany",
    "gibraltar": "Gibraltar",
    "greece": "Greece",
    "guernsey": "Guernsey",
    "hungary": "Hungary",
    "iceland": "Iceland",
    "ireland": "Ireland",
    "isle of man": "Isle of Man",
    "israel": "Israel",
    "italy": "Italy",
    "jersey": "Jersey",
    "kosovo": "Kosovo",
    "latvia": "Latvia",
    "liechtenstein": "Liechtenstein",
    "lithuania": "Lithuania",
    "luxembourg": "Luxembourg",
    "malta": "Malta",
    "moldova": "Moldova",
    "republic of moldova": "Moldova",
    "monaco": "Monaco",
    "montenegro": "Montenegro",
    "morocco": "Morocco",
    "netherlands": "Netherlands",
    "north macedonia": "North Macedonia",
    "republic of north macedonia": "North Macedonia",
    "northern ireland": "Northern Ireland",
    "norway": "Norway",
    "poland": "Poland",
    "portugal": "Portugal",
    "romania": "Romania",
    "russia": "Russia",
    "russian federation": "Russia",
    "san marino": "San Marino",
    "scotland": "Scotland",
    "serbia": "Serbia",
    "slovakia": "Slovakia",
    "slovak republic": "Slovakia",
    "slovenia": "Slovenia",
    "spain": "Spain",
    "sweden": "Sweden",
    "switzerland": "Switzerland",
    "turkey": "Turkey",
    "turkiye": "Turkey",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "ukraine": "Ukraine",
    "vatican": "Vatican",
    "wales": "Wales",
}


def resolve_canonical_country(raw_name: str) -> str | None:
    """Normalize a country string and return the OWID canonical name when known."""
    if not raw_name or not isinstance(raw_name, str):
        return None

    cleaned = raw_name.strip()
    normalized = unicodedata.normalize("NFKD", cleaned.lower())
    ascii_key = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_key = " ".join(ascii_key.split())

    return COUNTRY_MAP.get(ascii_key, cleaned.title())
