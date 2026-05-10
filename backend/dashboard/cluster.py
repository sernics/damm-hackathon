import math

import pandas as pd

from geo import choose_truck_size, haversine_km
from paths import DDI_MOLLET, OUT


def _seed_clusters(day, target_capacity=6.0):
    ordered = day.assign(
        angle=lambda df: df.apply(
            lambda row: math.atan2(row["lat"] - DDI_MOLLET["lat"], row["lon"] - DDI_MOLLET["lon"]),
            axis=1,
        )
    ).sort_values("angle")
    clusters = []
    current = []
    load = 0.0
    cluster_id = 0
    for row in ordered.itertuples():
        pallets = float(row.palets_total)
        if current and load + pallets > target_capacity:
            clusters.append((cluster_id, current))
            cluster_id += 1
            current = []
            load = 0.0
        current.append(row.Index)
        load += pallets
    if current:
        clusters.append((cluster_id, current))
    return clusters


def _centroid(df):
    load = df["palets_total"].clip(lower=0.01)
    return {
        "lat": float((df["lat"] * load).sum() / load.sum()),
        "lon": float((df["lon"] * load).sum() / load.sum()),
    }


def build_clusters():
    day = pd.read_parquet(OUT / "demo_day.parquet").copy()
    day = day.reset_index(drop=True)
    seed = _seed_clusters(day)
    assignments = {}
    for cluster_id, indexes in seed:
        for index in indexes:
            assignments[index] = cluster_id
    day["cluster_id"] = day.index.map(assignments)

    for _ in range(4):
        centers = {cluster_id: _centroid(group) for cluster_id, group in day.groupby("cluster_id")}
        loads = day.groupby("cluster_id")["palets_total"].sum().to_dict()
        for index, row in day.sample(frac=1, random_state=42).iterrows():
            current = row["cluster_id"]
            candidates = sorted(
                centers,
                key=lambda cid: haversine_km(row["lat"], row["lon"], centers[cid]["lat"], centers[cid]["lon"]),
            )
            for candidate in candidates:
                if candidate == current:
                    break
                if loads.get(candidate, 0.0) + row["palets_total"] <= 8.0:
                    loads[current] -= row["palets_total"]
                    loads[candidate] = loads.get(candidate, 0.0) + row["palets_total"]
                    day.at[index, "cluster_id"] = candidate
                    break

    loads = day.groupby("cluster_id")["palets_total"].sum()
    size_for = {cluster_id: choose_truck_size(load) for cluster_id, load in loads.items()}
    day["truck_size"] = day["cluster_id"].map(size_for)
    clusters = day.rename(columns={"palets_total": "pallets"})
    clusters["palets_total"] = clusters["pallets"]
    clusters.to_parquet(OUT / "clusters.parquet", index=False)
    print(
        f"Clusters: {clusters['cluster_id'].nunique()} trucks, "
        f"{clusters['palets_total'].sum():.1f} pallets, max load {loads.max():.1f}"
    )
    return clusters


if __name__ == "__main__":
    build_clusters()
