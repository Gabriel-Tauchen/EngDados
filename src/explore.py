from data_profiling import ProfileReport
from pathlib import Path
import pandas as pd
import re

# THE PATTERN TO CHANGE FOR EXPLORATION IS COVID19 OR AIR TAFFIC!!!!

BRONZE = Path("data/bronze/covid19") # to explore chagne to: bronze/covid19 or to bronze/air-traffic-EU
PATTERN = "owid-covid-data*.csv" # to explore change to: owid-covid-data*.csv or airport_traffic_20*.csv
FILE_NAME = re.compile(r"owid-covid-data(?:_(?P<date>\d{4}-\d{2}-\d{2}))?\.csv$") # to explore change to: owid-covid-data or airport_traffic_
REPORTS = Path("reports")

def most_recent_files_by_year():
    """Return the most recent extraction for each traffic year."""
    files_by_year = {}
    for path in BRONZE.glob(PATTERN):
        match = FILE_NAME.fullmatch(path.name)
        if not match:
            continue

        year = "covid19" # to eexplore change to: covid19 or int(match.group("year"))

        extraction_date = match.group("date") or "0000-00-00"
        candidate = (extraction_date, path.name, path)
        current = files_by_year.get(year)
        if current is None or candidate[:2] > current[:2]:
            files_by_year[year] = candidate

    if not files_by_year:
        raise FileNotFoundError(f"No CSV files found in {BRONZE}")

    return {year: candidate[2] for year, candidate in sorted(files_by_year.items())}

def generate_reports(files_by_year):
    """Generate a data profiling report for each recent file by year."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    reports = []
    for year, path in files_by_year.items():
        df = pd.read_csv(path)
        report = ProfileReport(df, title=f"{path.name}-{year}")
        report_path = REPORTS / f"{path.stem}.html"
        report.to_file(report_path)
        reports.append(report_path)
    return reports

def main():
    files_by_year = most_recent_files_by_year()
    reports = generate_reports(files_by_year)
    print("profiling reports generated for the following files:")
    for report in reports:
        print(report)

if __name__ == "__main__":
    main()