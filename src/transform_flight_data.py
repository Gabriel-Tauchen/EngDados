import re
from pathlib import Path

import pandas as pd

from cleaning import (
    calculate_percentage_change,
    create_text_key,
    format_date_column,
    strip_whitespace,
)
from country_mapping import resolve_canonical_country

BRONZE = Path("data/bronze/air-traffic-EU")
SILVER = Path("data/silver/air-traffic-EU")
PATTERN = "airport_traffic_*.csv"
MIN_YEAR = 2019


def load_latest_files_by_year() -> list[Path]:
    """Return the latest file for each year, starting from 2019."""
    files = sorted(BRONZE.glob(PATTERN))
    if not files:
        raise FileNotFoundError(f"No bronze flight files found in {BRONZE}")

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
        raise FileNotFoundError(f"No files from {MIN_YEAR} onward found in {BRONZE}")

    latest_files = [path for _, path in sorted(selected.values(), key=lambda item: item[1].name)]
    print(f"Selected flight files: {[file.name for file in latest_files]}")
    return latest_files


def load_flight_data() -> pd.DataFrame:
    """Load and concatenate the most recent bronze files for each year."""
    files = load_latest_files_by_year()
    frames = [pd.read_csv(file) for file in files]
    df = pd.concat(frames, ignore_index=True)
    print(f"Rows before cleaning: {len(df)}")
    return df


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
    processed["IFR_SHARE"] = (
        processed["TOTAL_IFR_FLIGHTS"] / processed["TOTAL_FLIGHTS"].replace(0, pd.NA) * 100
    ).fillna(0)

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
    print(f"Rows after duplicate removal: {len(deduplicated)}")
    return deduplicated


def save_silver(df: pd.DataFrame) -> Path:
    """Persist the cleaned flight dataset in the silver layer."""
    SILVER.mkdir(parents=True, exist_ok=True)
    destination = SILVER / f"air-traffic-EU-{pd.Timestamp.now().strftime('%Y%m%d-%H%M%S')}.parquet"
    df.to_parquet(destination, index=False)
    print(f"Saved flight silver file: {destination.name} | shape={df.shape}")
    return destination


def main() -> None:
    df = load_flight_data()
    df = build_flight_features(df)
    df = df[df["YEAR"].astype(str).isin([str(year) for year in range(MIN_YEAR, 2051)])].copy()
    df = drop_exact_duplicates(df)
    df = select_columns(df)
    save_silver(df)


if __name__ == "__main__":
    main()
