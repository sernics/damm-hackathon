import pandas as pd

from geo import choose_truck_size, route_distance_km
from paths import DDI_MOLLET, OUT


def _stop_records(group):
    ordered = group.sort_values(["entrega", "cliente"])
    return [
        {
            "seq": index + 1,
            "cliente": int(row.cliente),
            "name": row.nombre if pd.notna(row.nombre) else f"Client {row.cliente}",
            "lat": float(row.lat),
            "lon": float(row.lon),
            "pallets": float(row.palets_total),
            "entrega": int(row.entrega) if pd.notna(row.entrega) else index + 1,
        }
        for index, row in enumerate(ordered.itertuples())
    ]


def build_baseline():
    day = pd.read_parquet(OUT / "demo_day.parquet")
    records = []
    route_rows = []
    for transport, group in day.groupby("transporte"):
        stops = _stop_records(group)
        pallets = float(group["palets_total"].sum())
        truck_size = choose_truck_size(pallets)
        distance = route_distance_km(stops, DDI_MOLLET)
        occupation = pallets / truck_size if truck_size else 0.0
        records.append(
            {
                "cluster_id": str(transport),
                "transporte": str(transport),
                "ruta": str(group["ruta"].iloc[0]),
                "truck_size": truck_size,
                "stops": len(stops),
                "pallets": pallets,
                "distance_km": distance,
                "time_min": distance / 30 * 60,
                "occupation_pct": occupation * 100,
            }
        )
        for stop in stops:
            route_rows.append({**stop, "cluster_id": str(transport), "transport": str(transport)})
    summary = pd.DataFrame(records)
    routes = pd.DataFrame(route_rows)
    summary.to_parquet(OUT / "baseline_summary.parquet", index=False)
    routes.to_parquet(OUT / "baseline_routes.parquet", index=False)
    print(
        f"Baseline: {len(summary)} routes, {summary['distance_km'].sum():.1f} km, "
        f"{summary['pallets'].sum():.1f} pallets"
    )
    return summary, routes


if __name__ == "__main__":
    build_baseline()
