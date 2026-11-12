import importlib
import logging
import sys
import time
from pathlib import Path
from typing import Callable, Optional

# Ensure src directory is in path
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import BRONZE_COVID, BRONZE_FLIGHT, setup_logging
import enrich_data
import transform_covid_data
import transform_flight_data

log = logging.getLogger("pipeline")


def run_ingest() -> None:
    """Ingest raw datasets from Kaggle into the bronze layer."""
    log.info("Starting bronze ingestion from Kaggle...")
    try:
        import ingest_covid19
        ingest_flight = importlib.import_module("ingest_air-traffic-EU")

        ingest_covid19.main()
        ingest_flight.main()
    except Exception as exc:
        # If running offline or without credentials but bronze data is already present, warn and proceed
        if any(BRONZE_COVID.glob("*.csv")) and any(BRONZE_FLIGHT.glob("*.csv")):
            log.warning("Ingest could not refresh from Kaggle (%s), but bronze CSV files exist. Continuing.", exc)
        else:
            raise


def run_transform() -> None:
    """Clean and standardize bronze data into the silver layer (Parquet)."""
    log.info("Transforming COVID-19 data...")
    transform_covid_data.main()

    log.info("Transforming Air Traffic data...")
    transform_flight_data.main()


def run_enrich() -> None:
    """Enrich data by joining flight series with COVID context in the silver layer."""
    enrich_data.main()


# Explicit pipeline stages (declares what is done and what is pending for future classes)
STAGES = [
    ("ingest", run_ingest),
    ("transform", run_transform),
    ("enrich", run_enrich),
    ("load", None),       # Próximas aulas: carga em banco de dados relacional
    ("modeling", None),   # Próximas aulas: modelagem dimensional e camada Ouro
]

# Map aliases to support both English commands and Portuguese lecture names
STAGE_ALIASES = {
    "ingestao": "ingest",
    "transformacao": "transform",
    "enriquecimento": "enrich",
    "carga": "load",
    "modelagem": "modeling",
}


def execute_stage(name: str, func: Callable[[], None]) -> None:
    """Execute a single pipeline stage with timing and explicit error logging."""
    log.info("etapa %s: inicio", name)
    start_time = time.time()
    try:
        func()
    except Exception:
        log.exception("etapa %s falhou", name)
        raise
    elapsed = time.time() - start_time
    log.info("etapa %s: fim em %.2fs", name, elapsed)


def main(start_from: Optional[str] = None) -> None:
    """Run pipeline sequentially, optionally resuming from a specific stage."""
    setup_logging()

    target_stage = start_from.lower() if start_from else None
    target_stage = STAGE_ALIASES.get(target_stage, target_stage)

    valid_stage_names = [name for name, _ in STAGES]
    if target_stage and target_stage not in valid_stage_names:
        log.error(
            "Unknown stage '%s'. Available stages: %s",
            start_from,
            ", ".join(valid_stage_names),
        )
        sys.exit(1)

    started = target_stage is None

    for name, func in STAGES:
        if name == target_stage:
            started = True

        if not started or func is None:
            log.info("etapa %s: pulada", name)
            continue

        execute_stage(name, func)


if __name__ == "__main__":
    cli_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(cli_arg)
