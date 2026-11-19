import logging
from pathlib import Path
import duckdb

from config import (
    DB_PATH,
    SILVER_COVID,
    SILVER_ENRICHED,
    SILVER_FLIGHT,
)

logger = logging.getLogger(__name__)

# Silver layer parquet files mapped to table names
SILVER_TABLES = {
    "air_traffic_eu": SILVER_FLIGHT / "air-traffic-EU.parquet",
    "covid19": SILVER_COVID / "covid19.parquet",
    "flights_covid_enriched": SILVER_ENRICHED / "flights_covid_enriched.parquet",
}


def fetch_scalar(con: duckdb.DuckDBPyConnection, sql: str):
    """Execute SQL query and return the first column value of the first row."""
    return con.execute(sql).fetchone()[0]


def connect_db(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    """Connect to the in-process DuckDB analytical database file in the gold directory."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Database file path: %s", db_path)
    return duckdb.connect(str(db_path))


def create_schemas(con: duckdb.DuckDBPyConnection) -> None:
    """Create silver and gold analytical schemas in DuckDB."""
    for schema_name in ["silver", "gold"]:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    logger.info("Analytical schemas initialized: silver, gold")


def load_silver_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Load clean parquet files from the silver layer directly into DuckDB tables."""
    for table_name, file_path in SILVER_TABLES.items():
        if not file_path.exists():
            logger.warning("Silver dataset missing at %s, skipping table %s", file_path, table_name)
            continue

        path_posix = file_path.as_posix()
        con.execute(f"""
            CREATE OR REPLACE TABLE silver.{table_name} AS
            SELECT * FROM read_parquet('{path_posix}')
        """)
        row_count = fetch_scalar(con, f"SELECT COUNT(*) FROM silver.{table_name}")
        logger.info("silver.%s: %d rows loaded", table_name, row_count)



def build_gold_layer(con: duckdb.DuckDBPyConnection) -> None:
    """Build the dimensional star schema (dimensions, fact tables, and reporting views)."""
    # -------------------------------------------------------------------------
    # Dimensions (Context and descriptive attributes)
    # -------------------------------------------------------------------------
    # Country Dimension: Grain is exactly one row per country
    con.execute("""
        CREATE OR REPLACE TABLE gold.dim_country AS
        SELECT
            country_name                       AS country_id,
            iso_code                           AS iso_code,
            country_name                       AS country_name,
            ARG_MAX(continent, date)           AS continent,
            ARG_MAX(continent, date)           AS region,
            ARG_MAX(population, date)::BIGINT  AS population
        FROM silver.covid19
        WHERE country_name IS NOT NULL
        GROUP BY country_name, iso_code
    """)
    country_rows = fetch_scalar(con, "SELECT COUNT(*) FROM gold.dim_country")
    logger.info("gold.dim_country: %d rows", country_rows)

    # Airport Dimension: Grain is exactly one row per airport
    con.execute("""
        CREATE OR REPLACE TABLE gold.dim_airport AS
        SELECT
            APT_ICAO                      AS airport_id,
            ARG_MAX(APT_NAME, FLT_DATE)   AS airport_name,
            country_name                  AS country,
            ARG_MAX(STATE_NAME, FLT_DATE) AS state_name
        FROM silver.air_traffic_eu
        GROUP BY APT_ICAO, country_name
    """)
    airport_rows = fetch_scalar(con, "SELECT COUNT(*) FROM gold.dim_airport")
    logger.info("gold.dim_airport: %d rows", airport_rows)


    # -------------------------------------------------------------------------
    # Fact Tables (Measurements and metrics)
    # -------------------------------------------------------------------------
    # Fact 1: Annual country-level indicator fact (Grain: one country per year)
    con.execute("""
        CREATE OR REPLACE TABLE gold.fact_indicator AS
        WITH aggregates AS (
            SELECT
                country_name                        AS country_id,
                YEAR                                AS year,
                SUM(TOTAL_FLIGHTS)::BIGINT          AS value,
                SUM(TOTAL_FLIGHTS)::BIGINT          AS total_flights,
                SUM(TOTAL_IFR_FLIGHTS)::DOUBLE      AS total_ifr_flights,
                COALESCE(SUM(new_cases), 0)::DOUBLE AS new_cases,
                COALESCE(MAX(total_cases), 0)::BIGINT AS total_cases,
                COALESCE(SUM(new_deaths), 0)::DOUBLE  AS new_deaths,
                COALESCE(MAX(total_deaths), 0)::BIGINT AS total_deaths,
                ROUND(COALESCE(AVG(stringency_index), 0), 2) AS avg_stringency_index
            FROM silver.flights_covid_enriched
            WHERE country_name IS NOT NULL
            GROUP BY country_name, YEAR
        ),
        with_derivatives AS (
            SELECT
                country_id,
                year,
                value,
                total_flights,
                total_ifr_flights,
                new_cases,
                total_cases,
                new_deaths,
                total_deaths,
                avg_stringency_index,
                ROUND(
                    (value - LAG(value) OVER (PARTITION BY country_id ORDER BY year)) * 100.0 /
                    NULLIF(LAG(value) OVER (PARTITION BY country_id ORDER BY year), 0),
                    2
                ) AS pct_change,
                ROUND(
                    value * 100.0 / SUM(value) OVER (PARTITION BY year),
                    2
                ) AS region_share_pct
            FROM aggregates
        )
        SELECT * FROM with_derivatives
    """)
    indicator_rows = fetch_scalar(con, "SELECT COUNT(*) FROM gold.fact_indicator")
    logger.info("gold.fact_indicator: %d rows", indicator_rows)

    # Fact 2: Granular operational daily flight fact (Grain: one airport per date)
    con.execute("""
        CREATE OR REPLACE TABLE gold.fact_flights AS
        SELECT
            APT_ICAO                 AS airport_id,
            country_name             AS country_id,
            iso_code                 AS iso_code,
            FLT_DATE::DATE           AS flight_date,
            YEAR                     AS year,
            MONTH_NUM                AS month,
            TOTAL_FLIGHTS            AS total_flights,
            FLT_DEP_1                AS departures,
            FLT_ARR_1                AS arrivals,
            TOTAL_IFR_FLIGHTS        AS ifr_flights,
            IFR_SHARE                AS ifr_share_pct,
            flight_volume_pct_change AS flight_pct_change,
            new_cases                AS new_cases,
            total_cases              AS total_cases,
            new_deaths               AS new_deaths,
            total_deaths             AS total_deaths,
            stringency_index         AS stringency_index,
            flights_per_million_pop  AS flights_per_million_pop,
            flights_to_cases_ratio   AS flights_to_cases_ratio
        FROM silver.flights_covid_enriched
        WHERE country_name IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY APT_ICAO, FLT_DATE
            ORDER BY flight_volume_pct_change DESC
        ) = 1
    """)
    flight_rows = fetch_scalar(con, "SELECT COUNT(*) FROM gold.fact_flights")
    logger.info("gold.fact_flights: %d rows", flight_rows)

    # Audit records outside the pandemic coverage window (pre-2020 baseline and 2024 recovery)
    unmatched_covid = fetch_scalar(con, """
        SELECT COUNT(*) FROM silver.flights_covid_enriched
        WHERE iso_code IS NULL
    """)
    if unmatched_covid > 0:
        logger.warning(
            "%d silver records do not match COVID-19 timeline (expected: 2019 baseline and 2024 recovery)",
            unmatched_covid,
        )

    # -------------------------------------------------------------------------
    # Views: Flattened analytical views reconstructing joins on the fly
    # -------------------------------------------------------------------------
    con.execute("""
        CREATE OR REPLACE VIEW gold.vw_complete_indicator AS
        SELECT
            f.*,
            d.country_name,
            d.region,
            d.population
        FROM gold.fact_indicator f
        JOIN gold.dim_country d USING (country_id)
    """)
    logger.info("gold.vw_complete_indicator view created")

    con.execute("""
        CREATE OR REPLACE VIEW gold.vw_complete_flights AS
        SELECT
            f.*,
            a.airport_name,
            a.state_name,
            d.continent,
            d.population
        FROM gold.fact_flights f
        JOIN gold.dim_airport a USING (airport_id)
        JOIN gold.dim_country d USING (country_id)
    """)
    logger.info("gold.vw_complete_flights view created")


def validate_model_integrity(con: duckdb.DuckDBPyConnection) -> None:

    """Validate grain uniqueness and referential integrity (zero duplicates, zero orphans)."""
    # 1. Indicator Fact Grain: (country_id, year)
    duplicate_indicator_grain = fetch_scalar(con, """
        SELECT COUNT(*) FROM (
            SELECT country_id, year
            FROM gold.fact_indicator
            GROUP BY country_id, year
            HAVING COUNT(*) > 1
        )
    """)

    # 2. Indicator Fact Referential Integrity: check country dimension orphans
    orphan_indicator_country = fetch_scalar(con, """
        SELECT COUNT(*)
        FROM gold.fact_indicator f
        LEFT JOIN gold.dim_country d USING (country_id)
        WHERE d.country_id IS NULL
    """)

    # 3. Flight Fact Grain: (airport_id, flight_date)
    duplicate_flight_grain = fetch_scalar(con, """
        SELECT COUNT(*) FROM (
            SELECT airport_id, flight_date
            FROM gold.fact_flights
            GROUP BY airport_id, flight_date
            HAVING COUNT(*) > 1
        )
    """)

    # 4. Flight Fact Referential Integrity: check airport dimension orphans
    orphan_flight_airport = fetch_scalar(con, """
        SELECT COUNT(*)
        FROM gold.fact_flights f
        LEFT JOIN gold.dim_airport a USING (airport_id)
        WHERE a.airport_id IS NULL
    """)

    # 5. Flight Fact Referential Integrity: check country dimension orphans
    orphan_flight_country = fetch_scalar(con, """
        SELECT COUNT(*)
        FROM gold.fact_flights f
        LEFT JOIN gold.dim_country d USING (country_id)
        WHERE d.country_id IS NULL
    """)

    logger.info("Validation check - duplicate indicator pairs (country, year) : %d (expected: 0)", duplicate_indicator_grain)
    logger.info("Validation check - orphan indicator records without country   : %d (expected: 0)", orphan_indicator_country)
    logger.info("Validation check - duplicate flight pairs (airport, date)    : %d (expected: 0)", duplicate_flight_grain)
    logger.info("Validation check - orphan flight records without airport     : %d (expected: 0)", orphan_flight_airport)
    logger.info("Validation check - orphan flight records without country     : %d (expected: 0)", orphan_flight_country)

    total_violations = (
        duplicate_indicator_grain
        + orphan_indicator_country
        + duplicate_flight_grain
        + orphan_flight_airport
        + orphan_flight_country
    )

    if total_violations > 0:
        raise ValueError(
            f"Model integrity failure: "
            f"{duplicate_indicator_grain + duplicate_flight_grain} duplicates, "
            f"{orphan_indicator_country + orphan_flight_airport + orphan_flight_country} orphans"
        )


def main() -> None:
    """Load clean silver parquet tables into DuckDB database."""
    con = connect_db()
    try:
        create_schemas(con)
        load_silver_tables(con)
        # build_gold_layer(con)  # Retired: now handled declaratively by dbt (ecox14/)
    finally:
        con.close()
    logger.info("Silver tables loaded into DuckDB successfully")



if __name__ == "__main__":

    from config import setup_logging
    setup_logging()
    main()
