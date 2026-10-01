from pathlib import Path

import pandas as pd

from cleaning import (
    calculate_percentage_change,
    create_text_key,
    format_date_column,
    strip_whitespace,
)
from country_mapping import resolve_canonical_country

BRONZE = Path("data/bronze/covid19")
SILVER = Path("data/silver/covid19")
PATTERN = "owid-covid-data*.csv"


def load_latest_bronze_file() -> tuple[pd.DataFrame, Path]:
    """Load the most recent COVID bronze file."""
    files = sorted(BRONZE.glob(PATTERN))
    if not files:
        raise FileNotFoundError(f"No bronze COVID files found in {BRONZE}")

    latest_file = files[-1]
    df = pd.read_csv(latest_file)
    print(f"Loaded COVID bronze file: {latest_file.name} | shape={df.shape}")
    return df, latest_file


def keep_european_records(df: pd.DataFrame) -> pd.DataFrame:
    """Restrict the analysis to European countries only."""
    filtered = df[df["continent"].eq("Europe")].copy()
    print(f"Rows after Europe filter: {len(filtered)}")
    return filtered


def build_covid_features(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize text fields and derive analytical metrics for COVID data."""
    processed = strip_whitespace(df)
    processed["location_key"] = create_text_key(processed["location"])
    processed["country_name"] = processed["location"].apply(resolve_canonical_country)
    processed = format_date_column(processed, "date", "%Y-%m-%d")

    processed["population"] = pd.to_numeric(processed["population"], errors="coerce")
    processed["new_cases"] = pd.to_numeric(processed["new_cases"], errors="coerce").fillna(0)
    processed["total_cases"] = pd.to_numeric(processed["total_cases"], errors="coerce").fillna(0)
    processed["new_deaths"] = pd.to_numeric(processed["new_deaths"], errors="coerce").fillna(0)
    processed["total_deaths"] = pd.to_numeric(processed["total_deaths"], errors="coerce").fillna(0)

    processed["new_cases_per_million"] = (
        processed["new_cases"]
        / processed["population"].replace(0, pd.NA)
        * 1_000_000
    ).fillna(0)
    processed["total_cases_per_million"] = (
        processed["total_cases"]
        / processed["population"].replace(0, pd.NA)
        * 1_000_000
    ).fillna(0)

    processed["new_deaths_per_million"] = (
        processed["new_deaths"]
        / processed["population"].replace(0, pd.NA)
        * 1_000_000
    ).fillna(0)

    processed = calculate_percentage_change(
        processed,
        group_col="location_key",
        time_col="date",
        value_col="new_cases",
        target_col_name="new_cases_pct_change",
    )

    return processed


def select_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the core columns for COVID analysis."""
    keep = [
        "iso_code",
        "continent",
        "location",
        "country_name",
        "location_key",
        "date",
        "total_cases",
        "new_cases",
        "total_cases_per_million",
        "new_cases_per_million",
        "total_deaths",
        "new_deaths",
        "new_deaths_per_million",
        "population",
        "new_cases_pct_change",
    ]
    missing = [column for column in keep if column not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns for COVID output: {missing}")
    return df[keep].copy()


def save_silver(df: pd.DataFrame) -> Path:
    """Persist the cleaned COVID data in the silver layer as parquet."""
    SILVER.mkdir(parents=True, exist_ok=True)
    destination = SILVER / f"covid19-{pd.Timestamp.now().strftime('%Y%m%d-%H%M%S')}.parquet"
    df.to_parquet(destination, index=False)
    print(f"Saved COVID silver file: {destination.name} | shape={df.shape}")
    return destination


def main() -> None:
    df, _ = load_latest_bronze_file()
    df = keep_european_records(df)
    df = build_covid_features(df)
    df = select_columns(df)
    save_silver(df)


if __name__ == "__main__":
    main()
