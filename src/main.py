import argparse
import sys
import time
from pathlib import Path

# Add src to sys.path so modules can be imported directly
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import transform_covid_data
import transform_flight_data


def run_silver_pipeline():
    """Execute both silver transformation steps and report summary."""
    print("=" * 60)
    print("STARTING SILVER TRANSFORMATION PIPELINE")
    print("=" * 60)
    start_total = time.time()

    print("\n[1/2] Processing COVID-19 dataset...")
    t0 = time.time()
    covid_dest = transform_covid_data.main()
    print(f"COVID-19 Silver completed in {time.time() - t0:.2f}s -> {covid_dest}")

    print("\n[2/2] Processing Air Traffic EU dataset...")
    t0 = time.time()
    flight_dest = transform_flight_data.main()
    print(f"Air Traffic Silver completed in {time.time() - t0:.2f}s -> {flight_dest}")

    total_time = time.time() - start_total
    print("\n" + "=" * 60)
    print(f"SILVER PIPELINE FINISHED SUCCESSFULLY IN {total_time:.2f}s")
    print("=" * 60)


def run_ingest_pipeline():
    """Execute Kaggle ingestion scripts for bronze data."""
    print("=" * 60)
    print("STARTING BRONZE INGESTION PIPELINE (Requires Kaggle credentials)")
    print("=" * 60)
    try:
        import ingest_covid19
        import importlib
        ingest_air_traffic = importlib.import_module("ingest_air-traffic-EU")

        print("\n[1/2] Ingesting COVID-19...")
        ingest_covid19.main()

        print("\n[2/2] Ingesting Air Traffic EU...")
        ingest_air_traffic.main()
        print("\nIngestion completed successfully.")
    except Exception as exc:
        print(f"Ingestion failed or credentials missing: {exc}")
        raise


def main():
    parser = argparse.ArgumentParser(description="ECOX14 Data Engineering Pipeline Runner")
    parser.add_argument(
        "--stage",
        choices=["all", "silver", "ingest"],
        default="silver",
        help="Pipeline stage to execute (default: 'silver')",
    )
    args = parser.parse_args()

    if args.stage in ("all", "ingest"):
        run_ingest_pipeline()

    if args.stage in ("all", "silver"):
        run_silver_pipeline()


if __name__ == "__main__":
    main()
