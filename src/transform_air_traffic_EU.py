import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

BRONZE = Path("data/bronze/air-traffic-EU")
SILVER = Path("data/silver/air-traffic-EU")
PATTERN = "airport_traffic_*.csv"
MIN_YEAR = 2019

DEFAULT_KEEP_COLUMNS = [
    "YEAR",
    "MONTH_NUM",
    "MONTH_MON",
    "FLT_DATE",
    "APT_ICAO",
    "APT_NAME",
    "STATE_NAME",
    "FLT_DEP_1",
    "FLT_ARR_1",
    "FLT_TOT_1",
    "FLT_DEP_IFR_2",
    "FLT_ARR_IFR_2",
    "FLT_TOT_IFR_2",
]


def latest_files_by_year():
    """Return the newest bronze file for each year from 2019 onward."""
    files = sorted(BRONZE.glob(PATTERN))
    if not files:
        raise FileNotFoundError(f"No files found in {BRONZE} matching pattern {PATTERN}")

    selected = {}
    pattern = re.compile(r"airport_traffic_(\d{4})(?:_(\d{4}-\d{2}-\d{2}))?\.csv$")

    for path in files:
        match = pattern.fullmatch(path.name)
        if not match:
            continue

        year = int(match.group(1))
        if year < MIN_YEAR:
            continue

        extraction_date = match.group(2) or "0000-00-00"
        current = selected.get(year)
        if current is None or extraction_date > current[0]:
            selected[year] = (extraction_date, path)

    if not selected:
        raise FileNotFoundError(f"No files from {MIN_YEAR} onward found in {BRONZE}")

    return [path for _, path in sorted(selected.values(), key=lambda item: item[1].name)]


def load():
    """Load the selected yearly bronze files and return the concatenated DataFrame."""
    files = latest_files_by_year()
    frames = [pd.read_csv(path) for path in files]
    df = pd.concat(frames, ignore_index=True)
    print("Read files:", [path.name for path in files])
    print("Rows before cleaning:", df.shape)
    print("Columns:", df.columns.tolist())
    return df, files


def clean_columns(df):
    """Standardize column names and strip whitespace from text values."""
    df.columns = df.columns.str.strip()
    for column in df.select_dtypes(include=["object", "string"]).columns:
        df[column] = df[column].apply(lambda value: value.strip() if isinstance(value, str) else value)
    return df


def filter_2019_onward(df):
    """Keep only rows from 2019 onward, using the YEAR field as the source of truth."""
    before = len(df)
    valid = df["YEAR"].astype(str).isin([str(year) for year in range(MIN_YEAR, 2051)])
    df = df.loc[valid].copy()
    print(f"Rows after filtering year >= {MIN_YEAR}: {before} -> {len(df)}")
    return df


def select_columns(df, columns=None):
    """Keep only the columns needed for analysis and downstream joins."""
    keep = columns or DEFAULT_KEEP_COLUMNS
    missing = [column for column in keep if column not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns: {missing}")
    return df[keep].copy()


def convert_types(df):
    """Convert date and numeric columns to analysis-friendly dtypes."""
    df["YEAR"] = pd.to_numeric(df["YEAR"], errors="coerce").astype("Int64")
    df["MONTH_NUM"] = pd.to_numeric(df["MONTH_NUM"], errors="coerce").astype("Int64")
    df["FLT_DATE"] = pd.to_datetime(df["FLT_DATE"], format="%d-%m-%y", errors="coerce")
    for column in [
        "FLT_DEP_1",
        "FLT_ARR_1",
        "FLT_TOT_1",
        "FLT_DEP_IFR_2",
        "FLT_ARR_IFR_2",
        "FLT_TOT_IFR_2",
    ]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)
    return df


def check_key_temporal_series(df, key1="YEAR", key2="FLT_DATE"):
    """Ensure that the time series is unique by airport and date after removing exact duplicates."""
    df = df.drop_duplicates(ignore_index=True)
    if df.duplicated(subset=[key1, key2, "APT_ICAO"]).any():
        raise ValueError(f"Duplicate series found for {key1} + {key2} + APT_ICAO")
    print("Unique temporal series: YEAR + FLT_DATE + APT_ICAO")
    return df


def save(df):
    """Persist the cleaned dataset to the silver parquet layer."""
    SILVER.mkdir(parents=True, exist_ok=True)
    destination = SILVER / f"air-traffic-EU-{datetime.now().strftime('%Y%m%d-%H%M%S')}.parquet"
    df.to_parquet(destination, index=False)
    print("Saved:", destination.name, df.shape)
    return destination


def register(origin_files, destination, before, after, decisions):
    """Register the transformation with a provenance record."""
    info = {
        "origin_files": [path.name for path in origin_files],
        "silver_file": destination.name,
        "before": before,
        "after": after,
        "decisions": decisions,
        "transformation_date": datetime.now().isoformat(timespec="seconds"),
    }
    path = SILVER / "provenance.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")


def main():
    df, origin_files = load()
    before = len(df)
    df = clean_columns(df)
    df = filter_2019_onward(df)
    df = select_columns(df)
    df = convert_types(df)
    df = check_key_temporal_series(df)
    destination = save(df)
    register(origin_files, destination, before, len(df), [
        "clean_columns",
        "filter_2019_onward",
        "select_columns",
        "convert_types",
        "check_key_temporal_series",
    ])


if __name__ == "__main__":
    main()
