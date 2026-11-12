import json
import logging
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
from config import BRONZE_COVID, EUROCONTROL_ADDITIONAL_COUNTRIES, SILVER_COVID
from country_mapping import resolve_canonical_country

logger = logging.getLogger(__name__)
PATTERN = "owid-covid-data*.csv"


def load_latest_bronze_file() -> tuple[pd.DataFrame, Path]:
    """Load the most recent COVID bronze file."""
    files = sorted(BRONZE_COVID.glob(PATTERN))
    if not files:
        raise FileNotFoundError(f"No bronze COVID files found in {BRONZE_COVID}")

    latest_file = files[-1]
    df = pd.read_csv(latest_file)
    logger.info("Loaded COVID bronze file: %s | shape=%s", latest_file.name, df.shape)
    return df, latest_file


def keep_european_and_eurocontrol_records(df: pd.DataFrame) -> pd.DataFrame:
    """Restrict analysis to European countries and Eurocontrol partner countries."""
    is_europe = df["continent"].eq("Europe")
    is_eurocontrol_partner = df["location"].isin(EUROCONTROL_ADDITIONAL_COUNTRIES)
    filtered = df[is_europe | is_eurocontrol_partner].copy()
    logger.info("Rows after Europe & Eurocontrol partner filter: %d", len(filtered))
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
    SILVER_COVID.mkdir(parents=True, exist_ok=True)
    destination = SILVER_COVID / "covid19.parquet"
    df.to_parquet(destination, index=False)
    logger.info("Saved COVID silver file: %s | shape=%s", destination.name, df.shape)
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
    provenance_path = SILVER_COVID / "provenance.jsonl"
    with provenance_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")
    logger.info("Registered provenance in %s", provenance_path.name)


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
    from config import setup_logging
    setup_logging()
    main()
