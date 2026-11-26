import logging
from pathlib import Path

# Base project paths (dynamically calculated from this file's location)
ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
REPORTS_DIR = ROOT_DIR / "reports"
LOG_FILE = ROOT_DIR / "pipeline.log"
DB_PATH = GOLD_DIR / "project.duckdb"
DBT_DIR = ROOT_DIR / "ecox14"
DASHBOARD_DIR = ROOT_DIR / "dashboard"


# Dataset-specific paths

BRONZE_COVID = BRONZE_DIR / "covid19"
BRONZE_FLIGHT = BRONZE_DIR / "air-traffic-EU"
SILVER_COVID = SILVER_DIR / "covid19"
SILVER_FLIGHT = SILVER_DIR / "air-traffic-EU"
SILVER_ENRICHED = SILVER_DIR / "enriched"

# Eurocontrol partner countries monitored outside geographical Europe in OWID
EUROCONTROL_ADDITIONAL_COUNTRIES = {
    "Armenia",
    "Georgia",
    "Israel",
    "Morocco",
    "Turkey",
}


def setup_logging(log_file: Path = LOG_FILE, level: int = logging.INFO) -> logging.Logger:
    """Configure simultaneous logging to console and pipeline.log."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    return logging.getLogger("pipeline")

