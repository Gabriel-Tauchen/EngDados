from pathlib import Path
from datetime import date, datetime
import kagglehub
import shutil
import json

DATASET = "caesarmario/our-world-in-data-covid19-dataset"
BRONZE = Path("data/bronze/covid19")

def ingest():
    """Downloads the dataset from Kaggle and returns its local cache folder."""
    folder = kagglehub.dataset_download(DATASET)
    print(f"Downloading dataset from Kaggle in {folder}")
    return Path(folder)

def find(folder):
    """Finds all CSV files in the specified folder."""
    files = sorted(folder.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found")
    print(f"found: {[a.name for a in files]}")
    return files

def copy(origins):
    """Copies all origin files to the bronze layer."""
    BRONZE.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    destinations = []
    for origin in origins:
        destination = BRONZE / f"{origin.stem}_{today}{origin.suffix}"
        shutil.copy2(origin, destination)
        destinations.append(destination)
    return destinations

def register(origins, destinations):
    info = {
        "origin": DATASET,
        "files": [
            {
                "file_origin": origin.name,
                "file_bronze": destination.name,
            }
            for origin, destination in zip(origins, destinations)
        ],
        "extraction_date": datetime.now().isoformat(),
    }
    path = BRONZE / "source.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")

def main():
    folder = ingest()
    origins = find(folder)
    destinations = copy(origins)
    register(origins, destinations)

if __name__ == "__main__":
    main()