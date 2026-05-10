import json
from datetime import datetime

from baseline import build_baseline
from cluster import build_clusters
from demo_day import build_demo_dataset
from export import export_scenario
from loadplan import build_loadplans
from metrics import compare
from paths import OUT
from vrp import solve_clustered_routes, solve_historical_transports


SCENARIO_DATES = ["2026-02-26", "2026-02-27", "2026-03-02"]
DEFAULT_DATE = "2026-02-27"


def _label_for(date_value):
    return datetime.strptime(date_value, "%Y-%m-%d").strftime("%b %d, %Y")


def build_for_date(date_value):
    day = build_demo_dataset(date_value)
    if day.empty:
        raise ValueError(f"No deliveries found for {date_value}")
    build_baseline()
    solve_historical_transports()
    build_loadplans(date=date_value)
    compare()
    build_clusters()
    solve_clustered_routes()
    build_loadplans("clustered_routes.parquet", "clustered_summary.parquet", "clustered_loadplans.parquet", date=date_value)
    compare("clustered_summary.parquet", "clustered_metrics.parquet")
    safe_date = date_value.replace("-", "")
    export_scenario(
        "baseline_summary.parquet",
        "baseline_routes.parquet",
        f"scenario_{safe_date}_baseline.json",
        label="baseline",
        date=date_value,
    )
    export_scenario(
        "clustered_summary.parquet",
        "clustered_routes.parquet",
        f"scenario_{safe_date}_optimized.json",
        metrics_file="clustered_metrics.parquet",
        loadplans_file="clustered_loadplans.parquet",
        label="optimized",
        date=date_value,
    )


def build_all():
    OUT.mkdir(exist_ok=True)
    for date_value in SCENARIO_DATES:
        build_for_date(date_value)
    manifest = {
        "defaultDate": DEFAULT_DATE,
        "dates": [
            {
                "date": date_value,
                "label": _label_for(date_value),
                "baseline": f"scenario_{date_value.replace('-', '')}_baseline.json",
                "optimized": f"scenario_{date_value.replace('-', '')}_optimized.json",
            }
            for date_value in SCENARIO_DATES
        ],
    }
    with open(OUT / "scenario_manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    print(f"Built {len(SCENARIO_DATES)} scenario days")


if __name__ == "__main__":
    build_all()
