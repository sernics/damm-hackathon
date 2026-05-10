import json

import pandas as pd

from paths import DDI_MOLLET, DEMO_DATE, OUT

COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


def _jsonable(value):
    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if pd.isna(value) if not isinstance(value, (list, dict)) else False:
        return None
    return value


def _records_for_cluster(summary_row, routes, loadplans, index):
    cluster_id = str(summary_row.cluster_id)
    stops = routes[routes["cluster_id"].astype(str) == cluster_id].sort_values("seq")
    stop_records = []
    for row in stops.itertuples():
        stop_records.append(
            {
                "seq": int(row.seq),
                "cliente": int(row.cliente),
                "name": str(row.name),
                "lat": float(row.lat),
                "lon": float(row.lon),
                "pallets": round(float(row.pallets), 3),
            }
        )
    polyline = [[DDI_MOLLET["lon"], DDI_MOLLET["lat"]]]
    polyline.extend([[stop["lon"], stop["lat"]] for stop in stop_records])
    polyline.append([DDI_MOLLET["lon"], DDI_MOLLET["lat"]])
    plan = _jsonable(loadplans.get(cluster_id, {"truck_size": int(summary_row.truck_size), "pallets": []}))
    return {
        "id": cluster_id,
        "truck_size": int(summary_row.truck_size),
        "color": COLORS[index % len(COLORS)],
        "stops": stop_records,
        "polyline": polyline,
        "distance_km": round(float(summary_row.distance_km), 2),
        "time_min": round(float(summary_row.time_min), 1),
        "occupation_pct": round(float(summary_row.occupation_pct), 1),
        "load_plan": plan,
    }


def _kpis(summary, metrics=None):
    kpis = {
        "total_km": round(float(summary["distance_km"].sum()), 1),
        "avg_route_km": round(float(summary["distance_km"].mean()), 1),
        "avg_occupation_pct": round(float(summary["occupation_pct"].mean()), 1),
        "trucks_used": int(len(summary)),
        "total_pallets": round(float(summary["pallets"].sum()), 1),
        "total_time_min": round(float(summary["time_min"].sum()), 1),
    }
    if metrics:
        kpis.update({key: round(float(value), 1) if isinstance(value, float) else value for key, value in metrics.items()})
    return kpis


def export_scenario(summary_file, routes_file, json_file, metrics_file=None, loadplans_file=None, label="optimized", date=DEMO_DATE):
    summary = pd.read_parquet(OUT / summary_file)
    routes = pd.read_parquet(OUT / routes_file)
    loadplans = {}
    if loadplans_file and (OUT / loadplans_file).exists():
        for row in pd.read_parquet(OUT / loadplans_file).itertuples():
            loadplans[str(row.cluster_id)] = row.load_plan
    metrics = None
    if metrics_file and (OUT / metrics_file).exists():
        metrics = pd.read_parquet(OUT / metrics_file).iloc[0].to_dict()
    clusters = [
        _records_for_cluster(row, routes, loadplans, index)
        for index, row in enumerate(summary.sort_values("distance_km", ascending=False).itertuples())
    ]
    payload = {
        "metadata": {
            "date": date,
            "label": label,
            "n_transports": int(len(summary)),
            "n_clients": int(routes["cliente"].nunique()),
        },
        "depot": DDI_MOLLET,
        "clusters": clusters,
        "kpis": _kpis(summary, metrics),
    }
    with open(OUT / json_file, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(f"Exported {json_file}")
    return payload


if __name__ == "__main__":
    export_scenario(
        "baseline_summary.parquet",
        "baseline_routes.parquet",
        "scenario_baseline.json",
        label="baseline",
    )
    export_scenario(
        "optimized_summary.parquet",
        "optimized_routes.parquet",
        "scenario_optimized.json",
        metrics_file="metrics.parquet",
        loadplans_file="loadplans.parquet",
        label="optimized",
    )
