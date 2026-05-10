import pandas as pd

from paths import OUT

SLOT_NAMES = [
    "front-left",
    "front-right",
    "middle-left",
    "middle-right",
    "rear-left",
    "rear-right",
    "tail-left",
    "tail-right",
]


def _line_records(master, route, date):
    route = route[["cluster_id", "cliente", "seq"]].copy()
    route["cliente"] = route["cliente"].astype("Int64")
    lines = master.merge(route, on="cliente", how="inner")
    lines = lines[lines["fecha"] == pd.Timestamp(date)].copy()
    lines["size"] = lines["palets_ocupados"].clip(lower=0.001)
    return lines.sort_values(["cluster_id", "seq", "retornable", "familia"], ascending=[True, False, False, True])


def _pack_cluster(lines, truck_size):
    pallets = []
    for row in lines.itertuples():
        item = {
            "cliente": int(row.cliente),
            "material": str(row.material),
            "product": str(row.producto),
            "cantidad": float(row.cantidad),
            "uma": str(row.uma),
            "size": float(row.size),
            "stop_seq": int(row.seq),
            "retornable": bool(row.retornable),
        }
        candidates = sorted(
            range(len(pallets)),
            key=lambda idx: (pallets[idx]["first_unload_stop_seq"], pallets[idx]["occupation"]),
            reverse=True,
        )
        placed = False
        for idx in candidates:
            if pallets[idx]["occupation"] + item["size"] <= 1.0 + 1e-9:
                pallets[idx]["lines"].append(item)
                pallets[idx]["occupation"] += item["size"]
                pallets[idx]["first_unload_stop_seq"] = min(pallets[idx]["first_unload_stop_seq"], item["stop_seq"])
                placed = True
                break
        if not placed:
            pallets.append(
                {
                    "lines": [item],
                    "occupation": item["size"],
                    "first_unload_stop_seq": item["stop_seq"],
                }
            )
    pallets = sorted(pallets, key=lambda pallet: pallet["first_unload_stop_seq"])
    for index, pallet in enumerate(pallets):
        pallet["slot"] = index + 1
        pallet["position"] = SLOT_NAMES[min(index, len(SLOT_NAMES) - 1)]
        pallet["occupation_pct"] = round(min(pallet["occupation"], 1.0) * 100, 1)
        pallet.pop("occupation")
    return {"truck_size": int(truck_size), "pallets": pallets[: int(truck_size)]}


def build_loadplans(route_file="optimized_routes.parquet", summary_file="optimized_summary.parquet", out_file="loadplans.parquet", date="2026-02-27"):
    master = pd.read_parquet(OUT / "master.parquet")
    routes = pd.read_parquet(OUT / route_file)
    summary = pd.read_parquet(OUT / summary_file).set_index("cluster_id")
    line_rows = _line_records(master, routes, date)
    plans = []
    for cluster_id, lines in line_rows.groupby("cluster_id"):
        truck_size = summary.loc[str(cluster_id), "truck_size"] if str(cluster_id) in summary.index else 8
        plan = _pack_cluster(lines, truck_size)
        plans.append({"cluster_id": str(cluster_id), "load_plan": plan})
    out = pd.DataFrame(plans)
    out.to_parquet(OUT / out_file, index=False)
    print(f"Load plans: {len(out)} trucks")
    return out


if __name__ == "__main__":
    build_loadplans()
