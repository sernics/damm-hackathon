import pandas as pd

from geo import choose_truck_size, haversine_km, route_distance_km
from paths import DDI_MOLLET, OUT

try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
except Exception:
    pywrapcp = None
    routing_enums_pb2 = None


def _distance_matrix(nodes):
    matrix = []
    for a in nodes:
        row = []
        for b in nodes:
            row.append(int(haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) * 1000))
        matrix.append(row)
    return matrix


def _nearest_neighbor(stops):
    remaining = [dict(stop) for stop in stops]
    current = {"lat": DDI_MOLLET["lat"], "lon": DDI_MOLLET["lon"]}
    ordered = []
    while remaining:
        next_stop = min(
            remaining,
            key=lambda stop: haversine_km(current["lat"], current["lon"], stop["lat"], stop["lon"]),
        )
        remaining.remove(next_stop)
        ordered.append(next_stop)
        current = next_stop
    return ordered


def solve_stop_order(stops):
    if len(stops) <= 2 or pywrapcp is None:
        return _nearest_neighbor(stops)

    nodes = [{"lat": DDI_MOLLET["lat"], "lon": DDI_MOLLET["lon"]}] + [dict(stop) for stop in stops]
    matrix = _distance_matrix(nodes)
    manager = pywrapcp.RoutingIndexManager(len(nodes), 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        return matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    transit_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_index)
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_params.time_limit.FromSeconds(1)
    solution = routing.SolveWithParameters(search_params)
    if solution is None:
        return _nearest_neighbor(stops)

    ordered = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        if node != 0:
            ordered.append(nodes[node])
        index = solution.Value(routing.NextVar(index))
    return ordered


def _group_to_stops(group):
    stops = []
    for row in group.itertuples():
        stops.append(
            {
                "cliente": int(row.cliente),
                "name": row.nombre if pd.notna(row.nombre) else f"Client {row.cliente}",
                "lat": float(row.lat),
                "lon": float(row.lon),
                "pallets": float(row.palets_total),
                "entrega": int(row.entrega) if pd.notna(row.entrega) else 0,
            }
        )
    return stops


def solve_historical_transports():
    day = pd.read_parquet(OUT / "demo_day.parquet")
    summary_rows = []
    route_rows = []
    for transport, group in day.groupby("transporte"):
        stops = _group_to_stops(group)
        ordered = solve_stop_order(stops)
        for seq, stop in enumerate(ordered, start=1):
            stop["seq"] = seq
            route_rows.append({**stop, "cluster_id": str(transport), "transport": str(transport)})
        pallets = float(group["palets_total"].sum())
        truck_size = choose_truck_size(pallets)
        distance = route_distance_km(ordered, DDI_MOLLET)
        summary_rows.append(
            {
                "cluster_id": str(transport),
                "source": "historical_assignment",
                "truck_size": truck_size,
                "stops": len(ordered),
                "pallets": pallets,
                "distance_km": distance,
                "time_min": distance / 30 * 60,
                "occupation_pct": (pallets / truck_size) * 100,
            }
        )
    summary = pd.DataFrame(summary_rows)
    routes = pd.DataFrame(route_rows)
    summary.to_parquet(OUT / "optimized_summary.parquet", index=False)
    routes.to_parquet(OUT / "optimized_routes.parquet", index=False)
    print(f"Optimized A: {len(summary)} routes, {summary['distance_km'].sum():.1f} km")
    return summary, routes


def solve_clustered_routes():
    clusters = pd.read_parquet(OUT / "clusters.parquet")
    summary_rows = []
    route_rows = []
    for cluster_id, group in clusters.groupby("cluster_id"):
        stops = _group_to_stops(group)
        ordered = solve_stop_order(stops)
        for seq, stop in enumerate(ordered, start=1):
            stop["seq"] = seq
            route_rows.append({**stop, "cluster_id": str(cluster_id), "transport": str(cluster_id)})
        pallets = float(group["palets_total"].sum())
        truck_size = int(group["truck_size"].iloc[0])
        distance = route_distance_km(ordered, DDI_MOLLET)
        summary_rows.append(
            {
                "cluster_id": str(cluster_id),
                "source": "reclustered",
                "truck_size": truck_size,
                "stops": len(ordered),
                "pallets": pallets,
                "distance_km": distance,
                "time_min": distance / 30 * 60,
                "occupation_pct": (pallets / truck_size) * 100,
            }
        )
    summary = pd.DataFrame(summary_rows)
    routes = pd.DataFrame(route_rows)
    summary.to_parquet(OUT / "clustered_summary.parquet", index=False)
    routes.to_parquet(OUT / "clustered_routes.parquet", index=False)
    print(f"Optimized B: {len(summary)} routes, {summary['distance_km'].sum():.1f} km")
    return summary, routes


if __name__ == "__main__":
    solve_historical_transports()
