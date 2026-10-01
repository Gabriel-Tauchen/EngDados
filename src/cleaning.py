import unicodedata
from typing import Any

import pandas as pd


def strip_whitespace(df: pd.DataFrame) -> pd.DataFrame:
    """Remove leading and trailing spaces from column names and string values."""
    cleaned = df.copy()
    cleaned.columns = [str(column).strip() for column in cleaned.columns]

    for column in cleaned.select_dtypes(include=["object", "string"]).columns:
        cleaned[column] = cleaned[column].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )

    return cleaned


def create_text_key(series: pd.Series) -> pd.Series:
    """Create a normalized string key for safe text matching across datasets."""
    normalized = series.astype(str).str.strip().str.lower()
    normalized = normalized.apply(
        lambda value: unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return normalized


def apply_country_mapping(series: pd.Series, country_map: dict[str, str]) -> pd.Series:
    """Apply a manual country-name mapping to standardize labels."""
    return series.replace(country_map)


def format_date_column(
    df: pd.DataFrame, date_col: str, date_format: str = "%Y-%m-%d"
) -> pd.DataFrame:
    """Parse a date column into datetime dtype using an explicit format."""
    cleaned = df.copy()
    cleaned[date_col] = pd.to_datetime(
        cleaned[date_col], format=date_format, errors="coerce"
    )
    return cleaned


def calculate_percentage_change(
    df: pd.DataFrame,
    group_col: str,
    time_col: str,
    value_col: str,
    target_col_name: str,
) -> pd.DataFrame:
    """Compute the percentage change over time, sorted by group and time."""
    ordered = df.sort_values([group_col, time_col]).copy()
    ordered[target_col_name] = (
        ordered.groupby(group_col)[value_col].pct_change().fillna(0) * 100
    )
    return ordered


def categorize_by_quartile(
    df: pd.DataFrame,
    source_col: str,
    target_col: str,
    labels: list[str],
) -> pd.DataFrame:
    """Discretize a numeric series into quartile labels."""
    categorized = df.copy()
    categorized[target_col] = pd.qcut(categorized[source_col], q=4, labels=labels)
    return categorized
