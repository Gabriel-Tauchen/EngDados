import argparse
import os
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd

DATASET_CONFIGS = {
    "covid19": {
        "bronze_dir": Path("data/bronze/covid19"),
        "pattern": "owid-covid-data*.csv",
        "regex": re.compile(r"owid-covid-data(?:_(?P<date>\d{4}-\d{2}-\d{2}))?\.csv$"),
        "group_key": "covid19",
    },
    "air-traffic": {
        "bronze_dir": Path("data/bronze/air-traffic-EU"),
        "pattern": "airport_traffic_*.csv",
        "regex": re.compile(r"airport_traffic_(?P<year>\d{4})(?:_(?P<date>\d{4}-\d{2}-\d{2}))?\.csv$"),
        "group_key": "year",
    },
}


def find_most_recent_files(dataset_name: str) -> Dict[str, Path]:
    """Return the most recent extraction file for the specified dataset."""
    config = DATASET_CONFIGS.get(dataset_name)
    if not config:
        raise ValueError(f"Unknown dataset '{dataset_name}'. Available: {list(DATASET_CONFIGS.keys())}")

    bronze_dir: Path = config["bronze_dir"]
    pattern: str = config["pattern"]
    regex: re.Pattern = config["regex"]
    group_mode: str = config["group_key"]

    if not bronze_dir.exists():
        raise FileNotFoundError(f"Bronze directory does not exist: {bronze_dir}")

    files_by_group: Dict[str, tuple[str, str, Path]] = {}

    for path in bronze_dir.glob(pattern):
        match = regex.fullmatch(path.name)
        if not match:
            continue

        if group_mode == "year":
            group = match.group("year")
        else:
            group = dataset_name

        extraction_date = match.groupdict().get("date") or "0000-00-00"
        candidate = (extraction_date, path.name, path)
        current = files_by_group.get(group)

        if current is None or candidate[:2] > current[:2]:
            files_by_group[group] = candidate

    if not files_by_group:
        raise FileNotFoundError(f"No matching CSV files found in {bronze_dir}")

    return {group: candidate[2] for group, candidate in sorted(files_by_group.items())}


def generate_reports(files: Dict[str, Path], output_dir: Path) -> List[Path]:
    """Generate a data profiling report for each identified CSV file."""
    # Lazy import to avoid loading heavy profiling libraries during CLI argument parsing
    from data_profiling import ProfileReport

    output_dir.mkdir(parents=True, exist_ok=True)
    report_paths = []

    for label, path in files.items():
        print(f"Generating profiling report for {path.name} (label={label})...")
        df = pd.read_csv(path)
        report = ProfileReport(df, title=f"{path.name} ({label})", minimal=True)
        report_path = output_dir / f"{path.stem}_profile.html"
        report.to_file(report_path)
        report_paths.append(report_path)
        print(f"Saved report: {report_path}")

    return report_paths


def main():
    parser = argparse.ArgumentParser(description="Generate data profiling reports for bronze datasets.")
    parser.add_argument(
        "--dataset",
        choices=["covid19", "air-traffic", "all"],
        default="all",
        help="Dataset to profile: 'covid19', 'air-traffic', or 'all' (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports"),
        help="Directory to save generated HTML profiling reports (default: reports/)",
    )
    args = parser.parse_args()

    targets = ["covid19", "air-traffic"] if args.dataset == "all" else [args.dataset]

    all_reports = []
    for target in targets:
        print(f"\n--- Profiling {target} ---")
        files = find_most_recent_files(target)
        reports = generate_reports(files, args.output_dir)
        all_reports.extend(reports)

    print("\nProfiling completed successfully. Generated reports:")
    for report in all_reports:
        print(f"- {report}")


if __name__ == "__main__":
    main()
