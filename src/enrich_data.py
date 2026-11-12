import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

from config import SILVER_COVID, SILVER_ENRICHED, SILVER_FLIGHT

logger = logging.getLogger(__name__)


def load_silver_datasets() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load both cleaned silver datasets from parquet storage."""
    flight_file = SILVER_FLIGHT / "air-traffic-EU.parquet"
    covid_file = SILVER_COVID / "covid19.parquet"

    if not flight_file.exists():
        raise FileNotFoundError(f"Flight silver dataset missing: {flight_file}")
    if not covid_file.exists():
        raise FileNotFoundError(f"COVID silver dataset missing: {covid_file}")

    flight_df = pd.read_parquet(flight_file)
    covid_df = pd.read_parquet(covid_file)

    logger.info("Loaded flight silver dataset: %s | shape=%s", flight_file.name, flight_df.shape)
    logger.info("Loaded COVID silver dataset: %s | shape=%s", covid_file.name, covid_df.shape)
    return flight_df, covid_df


def inspect_keys_before_join(flight_df: pd.DataFrame, covid_df: pd.DataFrame) -> None:
    """Step 1 (Aula 2): Inspect join key sets before performing the merge."""
    flight_keys = set(zip(flight_df["country_name"], flight_df["FLT_DATE"]))
    covid_keys = set(zip(covid_df["country_name"], covid_df["date"]))

    only_in_flight = len(flight_keys - covid_keys)
    only_in_covid = len(covid_keys - flight_keys)
    in_both = len(flight_keys & covid_keys)

    logger.info("--- Step 1: Pre-join Key Verification ---")
    logger.info("Keys only in flight series : %d", only_in_flight)
    logger.info("Keys only in COVID context : %d", only_in_covid)
    logger.info("Keys present in both       : %d", in_both)


def merge_datasets(flight_df: pd.DataFrame, covid_df: pd.DataFrame) -> pd.DataFrame:
    """Step 2 (Aula 2): Execute left join declaring many_to_one relationship."""
    covid_cols = [
        "country_name",
        "date",
        "iso_code",
        "new_cases",
        "total_cases",
        "new_cases_per_million",
        "total_cases_per_million",
        "new_deaths",
        "total_deaths",
        "new_deaths_per_million",
        "stringency_index",
        "population",
    ]
    covid_subset = covid_df[covid_cols].drop_duplicates(subset=["country_name", "date"])

    logger.info("--- Step 2: Merging flight series with COVID context (how='left', validate='many_to_one') ---")
    merged = flight_df.merge(
        covid_subset,
        left_on=["country_name", "FLT_DATE"],
        right_on=["country_name", "date"],
        how="left",
        validate="many_to_one",
    )
    return merged


def validate_merge_counts(flight_df: pd.DataFrame, merged_df: pd.DataFrame) -> pd.DataFrame:
    """Step 3 & 4 (Aula 2): Validate row counts and analyze unmatched rows."""
    logger.info("--- Step 3: Validating Post-Merge Row Counts ---")
    logger.info("Series length before merge : %d", len(flight_df))
    logger.info("Result length after merge  : %d", len(merged_df))

    if len(flight_df) != len(merged_df):
        logger.warning("ATTENTION: Result length differs from original series! Grain shifted unexpectedly.")
    else:
        logger.info("Grain preserved perfectly: result row count matches flight series.")

    unmatched = merged_df["iso_code"].isna()
    unmatched_count = int(unmatched.sum())
    logger.info("Unmatched records without COVID pair: %d", unmatched_count)

    # Breakdown by year explains domain reasons for unmatched rows
    by_year = merged_df[unmatched]["YEAR"].value_counts().to_dict()
    logger.info("Unmatched breakdown by year: %s", by_year)
    return merged_df


def derive_post_merge_attributes(df: pd.DataFrame) -> pd.DataFrame:
    """Step 5 (Aula 2): Calculate attributes that only exist after joining the two sources."""
    logger.info("--- Step 5: Deriving Cross-Domain Post-Merge Attributes ---")
    enriched = df.copy()

    # 1. Daily airport flights normalized by national population (flights per million people)
    pop_in_millions = enriched["population"] / 1_000_000
    enriched["flights_per_million_pop"] = (
        (enriched["TOTAL_FLIGHTS"] / pop_in_millions.replace(0, np.nan))
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    # 2. Ratio of commercial flight operations relative to active daily COVID cases
    enriched["flights_to_cases_ratio"] = (
        (enriched["TOTAL_FLIGHTS"] / (enriched["new_cases"] + 1))
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    # Drop redundant join date column to keep schema clean
    if "date" in enriched.columns:
        enriched.drop(columns=["date"], inplace=True)

    logger.info("Derived attributes created: flights_per_million_pop, flights_to_cases_ratio")
    return enriched


def save_enriched_silver(df: pd.DataFrame) -> Path:
    """Step 6: Persist the enriched silver dataset to parquet and register provenance."""
    SILVER_ENRICHED.mkdir(parents=True, exist_ok=True)
    destination = SILVER_ENRICHED / "flights_covid_enriched.parquet"
    df.to_parquet(destination, index=False)
    logger.info("Saved enriched silver dataset: %s | shape=%s", destination.name, df.shape)

    provenance_info = {
        "left_series": "air-traffic-EU.parquet",
        "right_context": "covid19.parquet",
        "output_file": destination.name,
        "rows_total": len(df),
        "unmatched_rows": int(df["iso_code"].isna().sum()),
        "derived_attributes": ["flights_per_million_pop", "flights_to_cases_ratio"],
        "join_type": "left",
        "cardinality": "many_to_one",
        "transformation_date": datetime.now().isoformat(timespec="seconds"),
    }
    provenance_path = SILVER_ENRICHED / "provenance.jsonl"
    with provenance_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(provenance_info, ensure_ascii=False) + "\n")
    logger.info("Registered enrichment provenance in %s", provenance_path.name)
    return destination


def main() -> Path:
    flight_df, covid_df = load_silver_datasets()
    inspect_keys_before_join(flight_df, covid_df)
    merged = merge_datasets(flight_df, covid_df)
    validated = validate_merge_counts(flight_df, merged)
    enriched = derive_post_merge_attributes(validated)
    destination = save_enriched_silver(enriched)
    return destination


if __name__ == "__main__":
    from config import setup_logging
    setup_logging()
    main()
