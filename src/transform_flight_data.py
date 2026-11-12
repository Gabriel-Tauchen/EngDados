import json
import logging
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from cleaning import (
    calculate_percentage_change,
    create_text_key,
    format_date_column,
    strip_whitespace,
)
from config import BRONZE_FLIGHT, SILVER_FLIGHT
from country_mapping import resolve_canonical_country

logger = logging.getLogger(__name__)
PATTERN = "airport_traffic_*.csv"
MIN_YEAR = 2019


def load_latest_files_by_year() -> list[Path]:
    """Return the latest file for each year, starting from 2019."""
    files = sorted(BRONZE_FLIGHT.glob(PATTERN))
    if not files:
        raise FileNotFoundError(f"No bronze flight files found in {BRONZE_FLIGHT}")

    selected: dict[int, tuple[str, Path]] = {}
    file_pattern = re.compile(r"airport_traffic_(\d{4})(?:_(\d{4}-\d{2}-\d{2}))?\.csv$")

    for path in files:
        match = file_pattern.fullmatch(path.name)
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
        raise FileNotFoundError(f"No files from {MIN_YEAR} onward found in {BRONZE_FLIGHT}")

    latest_files = [path for _, path in sorted(selected.values(), key=lambda item: item[1].name)]
    logger.info("Selected flight files: %s", [file.name for file in latest_files])
    return latest_files


def load_flight_data() -> tuple[pd.DataFrame, list[Path]]:
    """Load and concatenate the most recent bronze files for each year."""
    files = load_latest_files_by_year()
    frames = [pd.read_csv(file) for file in files]
    df = pd.concat(frames, ignore_index=True)
    logger.info("Flight rows before cleaning: %d", len(df))
    return df, files


def build_flight_features(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize and derive features for flight analytics."""
    processed = strip_whitespace(df)
    processed["APT_ICAO_KEY"] = create_text_key(processed["APT_ICAO"])
    processed["APT_NAME_KEY"] = create_text_key(processed["APT_NAME"])
    processed["STATE_NAME_KEY"] = create_text_key(processed["STATE_NAME"])
    processed["country_name"] = processed["STATE_NAME"].apply(resolve_canonical_country)

    processed["FLT_DATE"] = pd.to_datetime(
        processed["FLT_DATE"], format="%d-%m-%y", errors="coerce"
    )

    for column in [
        "FLT_DEP_1",
        "FLT_ARR_1",
        "FLT_TOT_1",
        "FLT_DEP_IFR_2",
        "FLT_ARR_IFR_2",
        "FLT_TOT_IFR_2",
    ]:
        processed[column] = pd.to_numeric(processed[column], errors="coerce").fillna(0)

    processed["TOTAL_FLIGHTS"] = processed["FLT_DEP_1"] + processed["FLT_ARR_1"]
    processed["TOTAL_IFR_FLIGHTS"] = processed["FLT_DEP_IFR_2"] + processed["FLT_ARR_IFR_2"]

    ifr_share = processed["TOTAL_IFR_FLIGHTS"] / processed["TOTAL_FLIGHTS"].replace(0, np.nan) * 100
    processed["IFR_SHARE"] = (
        ifr_share.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    )

    processed = calculate_percentage_change(
        processed,
        group_col="APT_ICAO_KEY",
        time_col="FLT_DATE",
        value_col="TOTAL_FLIGHTS",
        target_col_name="flight_volume_pct_change",
    )

    return processed


def select_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Select the operational columns required for flight analysis."""
    keep = [
        "YEAR",
        "MONTH_NUM",
        "MONTH_MON",
        "FLT_DATE",
        "APT_ICAO",
        "APT_NAME",
        "STATE_NAME",
        "country_name",
        "FLT_DEP_1",
        "FLT_ARR_1",
        "FLT_TOT_1",
        "FLT_DEP_IFR_2",
        "FLT_ARR_IFR_2",
        "FLT_TOT_IFR_2",
        "TOTAL_FLIGHTS",
        "TOTAL_IFR_FLIGHTS",
        "IFR_SHARE",
        "flight_volume_pct_change",
    ]
    missing = [column for column in keep if column not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns for flight output: {missing}")
    return df[keep].copy()


def drop_exact_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Remove exact duplicate rows before preserving the temporal series."""
    deduplicated = df.drop_duplicates(ignore_index=True)
    logger.info("Flight rows after duplicate removal: %d", len(deduplicated))
    return deduplicated


def save_silver(df: pd.DataFrame) -> Path:
    """Persist the cleaned flight dataset in the silver layer as a canonical parquet file."""
    SILVER_FLIGHT.mkdir(parents=True, exist_ok=True)
    destination = SILVER_FLIGHT / "air-traffic-EU.parquet"
    df.to_parquet(destination, index=False)
    logger.info("Saved flight silver file: %s | shape=%s", destination.name, df.shape)
    return destination


def register_provenance(
    origins: list[Path], destination: Path, before: int, after: int, decisions: list[str]
) -> None:
    """Append transformation provenance and data lineage to provenance.jsonl."""
    info = {
        "origins": [origin.name for origin in origins],
        "silver_file": destination.name,
        "before": before,
        "after": after,
        "decisions": decisions,
        "transformation_date": datetime.now().isoformat(timespec="seconds"),
    }
    provenance_path = SILVER_FLIGHT / "provenance.jsonl"
    with provenance_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")
    logger.info("Registered provenance in %s", provenance_path.name)


def main() -> Path:
    df, origin_files = load_flight_data()
    before_count = len(df)

    df = build_flight_features(df)
    df = df[df["YEAR"].astype(str).isin([str(year) for year in range(MIN_YEAR, 2051)])].copy()
    df = drop_exact_duplicates(df)
    df = select_columns(df)
    destination = save_silver(df)

    decisions = [
        "select_latest_files_from_2019",
        "strip_whitespace",
        "resolve_canonical_country",
        "parse_flt_date",
        "calculate_totals_and_ifr_share",
        "calculate_percentage_change_safe_inf",
        "drop_exact_duplicates",
        "save_canonical_silver_parquet",
    ]
    register_provenance(origin_files, destination, before_count, len(df), decisions)
    return destination


if __name__ == "__main__":
    from config import setup_logging
    setup_logging()
    main()
