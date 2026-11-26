from pathlib import Path
import sys
from typing import Any, List, Optional
import duckdb
import pandas as pd

# Ensure src directory is accessible for configuration
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from config import DB_PATH
except ImportError:
    DB_PATH = ROOT_DIR / "data" / "gold" / "project.duckdb"


def get_connection(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    """Connect to the analytical DuckDB database in read-only mode by default."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Run pipeline load/modeling first.")
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def run_query(sql: str, params: Optional[List[Any]] = None) -> pd.DataFrame:
    """Execute a parameterized SQL query safely against DuckDB and return a Pandas DataFrame.

    All user-supplied values enter as parameters (?) to prevent SQL injection.
    Connection is opened and closed reliably per query in read-only mode.
    """
    con = get_connection(read_only=True)
    try:
        if params:
            return con.execute(sql, params).df()
        return con.execute(sql).df()
    finally:
        con.close()


def get_available_regions() -> List[str]:
    """Retrieve distinct regions from the indicators view."""
    df = run_query("""
        SELECT DISTINCT region
        FROM gold.vw_complete_indicator
        WHERE region IS NOT NULL
        ORDER BY region
    """)
    return df["region"].tolist()


def get_available_years() -> List[int]:
    """Retrieve distinct reporting years available in the gold layer."""
    df = run_query("""
        SELECT DISTINCT year
        FROM gold.vw_complete_indicator
        ORDER BY year DESC
    """)
    return [int(y) for y in df["year"].tolist()]


def get_available_countries(region: Optional[str] = None) -> List[str]:
    """Retrieve distinct country names, optionally filtered by geographic region."""
    if region and region != "All":
        df = run_query("""
            SELECT DISTINCT country_name
            FROM gold.vw_complete_indicator
            WHERE region = ?
            ORDER BY country_name
        """, [region])
    else:
        df = run_query("""
            SELECT DISTINCT country_name
            FROM gold.vw_complete_indicator
            ORDER BY country_name
        """)
    return df["country_name"].tolist()


def get_indicators_by_region_and_year(region: str, year: int) -> pd.DataFrame:
    """Query country indicators for a specific region and year, ordered by total flight volume."""
    if region == "All":
        sql = """
            SELECT
                country_name,
                year,
                total_flights,
                COALESCE(pct_change, 0) AS pct_change,
                region_share_pct,
                new_cases,
                avg_stringency_index,
                population
            FROM gold.vw_complete_indicator
            WHERE year = ?
            ORDER BY total_flights DESC
        """
        return run_query(sql, [year])

    sql = """
        SELECT
            country_name,
            year,
            total_flights,
            COALESCE(pct_change, 0) AS pct_change,
            region_share_pct,
            new_cases,
            avg_stringency_index,
            population
        FROM gold.vw_complete_indicator
        WHERE region = ? AND year = ?
        ORDER BY total_flights DESC
    """
    return run_query(sql, [region, year])


def get_flight_trend_by_country(country_name: str) -> pd.DataFrame:
    """Retrieve multi-year trajectory for a single country or all countries combined (2019-2024)."""
    if country_name in ("All", "All Countries", "All Countries (Aggregated)", "All (Aggregated)"):
        sql = """
            SELECT
                year,
                SUM(total_flights) AS total_flights,
                ROUND(COALESCE(
                    (SUM(total_flights) - LAG(SUM(total_flights)) OVER (ORDER BY year)) * 100.0 /
                    NULLIF(LAG(SUM(total_flights)) OVER (ORDER BY year), 0),
                    0
                ), 2) AS pct_change,
                COALESCE(SUM(new_cases), 0) AS new_cases,
                ROUND(COALESCE(AVG(avg_stringency_index), 0), 2) AS avg_stringency
            FROM gold.vw_complete_indicator
            GROUP BY year
            ORDER BY year ASC
        """
        return run_query(sql)

    sql = """
        SELECT
            year,
            total_flights,
            COALESCE(pct_change, 0) AS pct_change,
            new_cases,
            avg_stringency_index
        FROM gold.vw_complete_indicator
        WHERE country_name = ?
        ORDER BY year ASC
    """
    return run_query(sql, [country_name])



def get_top_airports(year: int, limit: int = 10, country_name: Optional[str] = None) -> pd.DataFrame:
    """Retrieve top airports ranked by total operational flights for a given year."""
    if country_name and country_name != "All":
        sql = """
            SELECT
                airport_name,
                airport_id,
                country_id,
                SUM(total_flights) AS total_flights,
                SUM(departures) AS departures,
                SUM(arrivals) AS arrivals,
                ROUND(AVG(ifr_share_pct), 2) AS avg_ifr_share_pct
            FROM gold.vw_complete_flights
            WHERE year = ? AND country_id = ?
            GROUP BY airport_name, airport_id, country_id
            ORDER BY total_flights DESC
            LIMIT ?
        """
        return run_query(sql, [year, country_name, limit])

    sql = """
        SELECT
            airport_name,
            airport_id,
            country_id,
            SUM(total_flights) AS total_flights,
            SUM(departures) AS departures,
            SUM(arrivals) AS arrivals,
            ROUND(AVG(ifr_share_pct), 2) AS avg_ifr_share_pct
        FROM gold.vw_complete_flights
        WHERE year = ?
        GROUP BY airport_name, airport_id, country_id
        ORDER BY total_flights DESC
        LIMIT ?
    """
    return run_query(sql, [year, limit])


def get_summary_metrics(region: Optional[str] = None, year: Optional[int] = None) -> dict:
    """Calculate aggregated headline KPIs for the dashboard filters."""
    where_clauses = []
    params: List[Any] = []

    if region and region != "All":
        where_clauses.append("region = ?")
        params.append(region)

    if year is not None:
        where_clauses.append("year = ?")
        params.append(year)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    sql = f"""
        SELECT
            COALESCE(SUM(total_flights), 0)::BIGINT AS total_flights,
            COALESCE(SUM(new_cases), 0)::BIGINT AS total_new_cases,
            ROUND(COALESCE(AVG(avg_stringency_index), 0), 2) AS avg_stringency,
            COUNT(DISTINCT country_id) AS country_count
        FROM gold.vw_complete_indicator
        {where_sql}
    """
    df = run_query(sql, params if params else None)
    if not df.empty:
        row = df.iloc[0]
        return {
            "total_flights": int(row["total_flights"]),
            "total_new_cases": int(row["total_new_cases"]),
            "avg_stringency": float(row["avg_stringency"]),
            "country_count": int(row["country_count"]),
        }
    return {
        "total_flights": 0,
        "total_new_cases": 0,
        "avg_stringency": 0.0,
        "country_count": 0,
    }


def get_multivariate_timeline(
    country_name: str,
    granularity: str = "month",
    start_year: int = 2019,
    end_year: int = 2024,
    region: Optional[str] = None,
) -> pd.DataFrame:
    """Retrieve temporal overlay series (flights, COVID-19 cases, stringency index).

    Supports individual countries or aggregated data across all countries (or a region).
    Supports monthly or yearly granularity for multi-indicator correlation analysis.
    """
    is_all_countries = country_name in (
        "All",
        "All Countries",
        "All Countries (Aggregated)",
        "All (Aggregated)",
    )

    if granularity == "year":
        where_clauses = ["year BETWEEN ? AND ?"]
        params: List[Any] = [start_year, end_year]

        if not is_all_countries:
            where_clauses.append("country_name = ?")
            params.append(country_name)
        elif region and region != "All":
            where_clauses.append("region = ?")
            params.append(region)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT
                year::VARCHAR AS period,
                SUM(total_flights) AS total_flights,
                COALESCE(SUM(new_cases), 0) AS new_cases,
                ROUND(COALESCE(AVG(avg_stringency_index), 0), 2) AS avg_stringency
            FROM gold.vw_complete_indicator
            WHERE {where_sql}
            GROUP BY year
            ORDER BY year ASC
        """
        return run_query(sql, params)

    # Monthly granularity from vw_complete_flights
    where_clauses = ["year BETWEEN ? AND ?"]
    params = [start_year, end_year]

    if not is_all_countries:
        where_clauses.append("country_id = ?")
        params.append(country_name)
    elif region and region != "All":
        where_clauses.append("continent = ?")
        params.append(region)

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT
            strftime(DATE_TRUNC('month', flight_date), '%Y-%m') AS period,
            SUM(total_flights) AS total_flights,
            COALESCE(SUM(new_cases), 0) AS new_cases,
            ROUND(COALESCE(AVG(stringency_index), 0), 2) AS avg_stringency
        FROM gold.vw_complete_flights
        WHERE {where_sql}
        GROUP BY DATE_TRUNC('month', flight_date)
        ORDER BY period ASC
    """
    return run_query(sql, params)



def normalize_series_min_max(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Normalize specified columns into a 0-100 scale to enable direct visual comparison."""
    norm_df = df.copy()
    for col in columns:
        if col in norm_df.columns and pd.api.types.is_numeric_dtype(norm_df[col]):
            min_val = float(norm_df[col].min())
            max_val = float(norm_df[col].max())
            if max_val > min_val:
                norm_df[col] = ((norm_df[col] - min_val) / (max_val - min_val)) * 100.0
            else:
                norm_df[col] = 100.0 if max_val > 0 else 0.0
    return norm_df

