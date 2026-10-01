import json
from datetime import datetime
from pathlib import Path

import pandas as pd

BRONZE = Path("data/bronze/covid19")
SILVER = Path("data/silver/covid19")
PATTERN = "owid-covid-data*.csv"

def load():
    """"Loads the COVID-19 data from the bronze layer and returns a DataFrame."""
    files = sorted(BRONZE.glob(PATTERN))
    if not files:
        raise FileNotFoundError(f"No files found in {BRONZE} matching pattern {PATTERN}")
    path = files[-1]
    df = pd.read_csv(path)
    print("Read:", path.name, df.shape)

    print("Columns:", df.columns.tolist())
    print("Missing values:", df.isna().sum())

    return df, path

def remove_spaces(df):
    """ Removes leading and trailing spaces from column names and string values in the DataFrame."""
    df.columns = df.columns.str.strip()
    for column in df.select_dtypes(include=["object", "string"]).columns:
        df[column] = df[column].apply(lambda value: value.strip() if isinstance(value, str) else value)
    return df

def remove_non_european_countries(df):
    """Filters the contries that are not european by using the 'continent' column."""
    european_contries = df['continent'] == 'Europe'
    print("Non-European countries removed:", df.shape[0] - european_contries.sum())
    print("Remaining countries:", european_contries.sum())
    return df[european_contries].copy()

def check_key_temporal_series(df, key1="iso_code", key2="date"):
    """Checks if the combination of key1 and key2 is unique in the DataFrame."""
    if not df.duplicated(subset=[key1, key2]).any():
        print(f"Unique temporal series: {key1} + {key2}")
    else:
        raise ValueError(f"Duplicated temporal series found for {key1} + {key2}")
    return df.drop_duplicates(subset=[key1, key2])

def convert_types(df):
    """Converts the types of specific columns in the DataFrame."""
    for column in ["date"]:
        df[column] = pd.to_datetime(df[column], errors='coerce')
    return df

def iqr_limits(series):
    """Calculates the lower and upper limits for outlier detection using the IQR method."""
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower_limit = q1 - 1.5 * iqr
    upper_limit = q3 + 1.5 * iqr
    return lower_limit, upper_limit

def mark_outliers(df, column):
    """Marks outliers in the specified column of the DataFrame using the IQR method."""
    lower_limit, upper_limit = iqr_limits(df[column])
    df[f"{column}_outlier"] = (df[column] < lower_limit) | (df[column] > upper_limit)
    print(f"Outliers marked in column '{column}': {df[f'{column}_outlier'].sum()}")
    return df

def mark_zscore(df, column, threshold=3):
    """Marks outliers in the specified column of the DataFrame using the Z-score method."""
    z = (df[column] - df[column].mean()) / df[column].std()
    df[column + "_z"] = z.abs() > threshold
    print(column, "z above", threshold, ":", df[column + "_z"].sum())
    return df

def remove_errors(df, column, minimum, maximum):
    """Removes rows from the DataFrame where the specified column has values outside the given range."""
    valid = df[column].between(minimum, maximum)
    print("removed:", (~valid).sum())
    return df[valid].copy()

def save(df):
    """ Saves the DataFrame to the silver layer in Parquet format with a timestamped filename."""
    SILVER.mkdir(parents=True, exist_ok=True)
    destination = SILVER / f"covid19-{datetime.now().strftime('%Y%m%d-%H%M%S')}.parquet"
    df.to_parquet(destination, index=False)
    print("Saved:", destination.name, df.shape)
    return destination

def register(origin, destination, before, after, decisions):
    """Registers the transformation in a JSON file."""
    info = {
        "origin": origin.name,
        "silver_file": destination.name,
        "before": before,
        "after": after,
        "decisions": decisions,
        "transformation_date": datetime.now().isoformat(timespec='seconds'),
    }
    path = SILVER / "provenance.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")


def main():
    df, origin = load()
    before = len(df)
    df = remove_spaces(df)
    df = remove_non_european_countries(df)
    df = check_key_temporal_series(df)
    df = convert_types(df)
    destination = save(df)
    register(origin, destination, before, len(df), [
        "remove_spaces",
        "remove_non_european_countries",
        "check_key_temporal_series",
        "convert_types"
    ])


if __name__ == "__main__":
    main()