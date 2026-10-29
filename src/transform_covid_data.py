import json
from datetime import datetime
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

# Eurocontrol member or monitored partner states that OWID classifies in Asia or Africa
EUROCONTROL_ADDITIONAL_COUNTRIES = {
    "Armenia",
    "Georgia",
    "Israel",
    "Morocco",
    "Turkey",
}


def load_latest_bronze_file() -> tuple[pd.DataFrame, Path]:
    """Load the most recent COVID bronze file."""
    files = sorted(BRONZE.glob(PATTERN))
    if not files:
        raise FileNotFoundError(f"No bronze COVID files found in {BRONZE}")

    latest_file = files[-1]
    df = pd.read_csv(latest_file)
    print(f"Loaded COVID bronze file: {latest_file.name} | shape={df.shape}")
    return df, latest_file


def keep_european_and_eurocontrol_records(df: pd.DataFrame) -> pd.DataFrame:
    """Restrict analysis to European countries and Eurocontrol partner countries."""
    is_europe = df["continent"].eq("Europe")
    is_eurocontrol_partner = df["location"].isin(EUROCONTROL_ADDITIONAL_COUNTRIES)
    filtered = df[is_europe | is_eurocontrol_partner].copy()
    print(f"Rows after Europe & Eurocontrol partner filter: {len(filtered)}")
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

    # Stringency index: Oxford Coronavirus Government Response Tracker (0-100)
    if "stringency_index" in processed.columns:
        processed["stringency_index"] = pd.to_numeric(
            processed["stringency_index"], errors="coerce"
        ).fillna(0)
    else:
        processed["stringency_index"] = 0.0

    import numpy as np

    pop_series = processed["population"].replace(0, np.nan)
    processed["new_cases_per_million"] = (
        (processed["new_cases"] / pop_series * 1_000_000).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    )
    processed["total_cases_per_million"] = (
        (processed["total_cases"] / pop_series * 1_000_000).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    )
    processed["new_deaths_per_million"] = (
        (processed["new_deaths"] / pop_series * 1_000_000).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    )

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
        "stringency_index",
        "population",
        "new_cases_pct_change",
    ]
    missing = [column for column in keep if column not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns for COVID output: {missing}")
    return df[keep].copy()


def save_silver(df: pd.DataFrame) -> Path:
    """Persist the cleaned COVID data in the silver layer as a canonical parquet file."""
    SILVER.mkdir(parents=True, exist_ok=True)
    destination = SILVER / "covid19.parquet"
    df.to_parquet(destination, index=False)
    print(f"Saved COVID silver file: {destination.name} | shape={df.shape}")
    return destination


def register_provenance(
    origin: Path, destination: Path, before: int, after: int, decisions: list[str]
) -> None:
    """Append transformation provenance and data lineage to provenance.jsonl."""
    info = {
        "origin": origin.name,
        "silver_file": destination.name,
        "before": before,
        "after": after,
        "decisions": decisions,
        "transformation_date": datetime.now().isoformat(timespec="seconds"),
    }
    provenance_path = SILVER / "provenance.jsonl"
    with provenance_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")
    print(f"Registered provenance in {provenance_path.name}")


def main() -> Path:
    raw_df, origin_file = load_latest_bronze_file()
    before_count = len(raw_df)

    df = keep_european_and_eurocontrol_records(raw_df)
    df = build_covid_features(df)
    df = select_columns(df)
    destination = save_silver(df)

    decisions = [
        "strip_whitespace",
        "keep_european_and_eurocontrol_records",
        "resolve_canonical_country",
        "format_date_column",
        "include_stringency_index",
        "calculate_percentage_change_safe_inf",
        "save_canonical_silver_parquet",
    ]
    register_provenance(origin_file, destination, before_count, len(df), decisions)
    return destination


if __name__ == "__main__":
    main()
