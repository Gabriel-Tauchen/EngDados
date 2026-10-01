from pathlib import Path

import pandas as pd


def load_csv(path: str | Path) -> pd.DataFrame:
    """Load a CSV file from disk and return a DataFrame."""
    return pd.read_csv(path)


def check_structure(df: pd.DataFrame, expected_columns: list[str] | None = None) -> None:
    """Print a quick diagnostic summary for a bronze dataset without altering the pipeline."""
    print("Shape:", df.shape)
    print("Columns:", list(df.columns))
    print("Dtypes:\n", df.dtypes)

    if expected_columns:
        missing = [column for column in expected_columns if column not in df.columns]
        if missing:
            print("Missing columns:", missing)
        else:
            print("All expected columns are present.")


if __name__ == "__main__":
    bronze_file = Path("data/bronze/covid19/owid-covid-data_2026-08-27.csv")
    df = load_csv(bronze_file)
    check_structure(
        df,
        expected_columns=[
            "iso_code",
            "continent",
            "location",
            "date",
            "total_cases",
            "new_cases",
        ],
    )
