"""Build dashboard scenario JSONs from the FFD truck plan.

Source of truth for the optimized scenarios is the `truck_plan_normalized.json`
produced on the `clustering` branch (now copied to
`data/custom/ffd/truck_plan_normalized.json`). The file contains, for every
delivery day, a list of trucks; each truck is a list of client entries with
`client_name`, `transport_ids` and `pallet_equiv`.

This script joins those entries with the existing master/geocoded parquets so
we can fill in everything the front-end expects (cliente id, lat/lon, ordered
stops, polyline, distances, load plan lines, KPIs) without changing
`frontend/`.

Outputs (under `outputs/`):
    scenario_<YYYYMMDD>_baseline.json
    scenario_<YYYYMMDD>_optimized.json
    scenario_manifest.json
"""

from __future__ import annotations

import ast
import json
import math
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
FFD_FILE = ROOT / "data" / "custom" / "ffd" / "truck_plan_normalized.json"
MASTER_FILE = OUT / "master.parquet"
GEOCODED_FILE = OUT / "geocoded.parquet"

DDI_MOLLET = {"lat": 41.5417, "lon": 2.2126, "name": "DDI Mollet"}
TRUCK_SIZES = (3, 6, 8)
COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]
SLOT_NAMES = [
    "front-left", "front-right",
    "middle-left", "middle-right",
    "rear-left", "rear-right",
    "tail-left", "tail-right",
]
CO2_KG_PER_KM = 0.9
URBAN_KMH = 30
MIN_LINE_SIZE = 0.001
DEFAULT_DATE = "2026-02-27"


def strip_accents(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(c)
    )


def norm_name(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return " ".join(strip_accents(str(value)).upper().strip().split())


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def choose_truck_size(pallets: float) -> int:
    for size in TRUCK_SIZES:
        if pallets <= size + 1e-9:
            return size
    largest = max(TRUCK_SIZES)
    return int(math.ceil(pallets / largest) * largest)


def nearest_neighbor_order(stops: list[dict], depot: dict) -> list[dict]:
    if not stops:
        return []
    remaining = stops.copy()
    ordered: list[dict] = []
    cur_lat, cur_lon = depot["lat"], depot["lon"]
    while remaining:
        idx, _ = min(
            enumerate(remaining),
            key=lambda pair: haversine_km(cur_lat, cur_lon, pair[1]["lat"], pair[1]["lon"]),
        )
        nxt = remaining.pop(idx)
        ordered.append(nxt)
        cur_lat, cur_lon = nxt["lat"], nxt["lon"]
    return ordered


def polyline_for(stops: list[dict], depot: dict) -> list[list[float]]:
    poly = [[depot["lon"], depot["lat"]]]
    poly.extend([[stop["lon"], stop["lat"]] for stop in stops])
    poly.append([depot["lon"], depot["lat"]])
    return poly


def route_distance_km(stops: list[dict], depot: dict) -> float:
    if not stops:
        return 0.0
    coords = [(depot["lat"], depot["lon"])]
    coords.extend((stop["lat"], stop["lon"]) for stop in stops)
    coords.append((depot["lat"], depot["lon"]))
    return sum(haversine_km(a[0], a[1], b[0], b[1]) for a, b in zip(coords, coords[1:]))


def pack_pallets(line_records: list[dict], truck_size: int) -> dict:
    """First-fit decreasing pack of `lines` into pallets of size 1.0."""
    pallets: list[dict] = []
    for item in sorted(
        line_records,
        key=lambda line: (-line["stop_seq"], not line["retornable"], line["material"]),
    ):
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
                pallets[idx]["first_unload_stop_seq"] = min(
                    pallets[idx]["first_unload_stop_seq"], item["stop_seq"]
                )
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

    pallets.sort(key=lambda pallet: pallet["first_unload_stop_seq"])
    for index, pallet in enumerate(pallets):
        pallet["slot"] = index + 1
        pallet["position"] = SLOT_NAMES[min(index, len(SLOT_NAMES) - 1)]
        pallet["occupation_pct"] = round(min(pallet["occupation"], 1.0) * 100, 1)
        pallet.pop("occupation")
    return {"truck_size": int(truck_size), "pallets": pallets[: int(truck_size)]}


def line_record(row: pd.Series, stop_seq: int) -> dict:
    size = float(row["palets_ocupados"]) if pd.notna(row["palets_ocupados"]) else 0.0
    size = max(size, MIN_LINE_SIZE)
    return {
        "cantidad": float(row["cantidad"]),
        "cliente": int(row["cliente"]),
        "material": str(row["material"]),
        "product": str(row["producto"]) if pd.notna(row["producto"]) else "",
        "retornable": bool(row["retornable"]),
        "size": size,
        "stop_seq": int(stop_seq),
        "uma": str(row["uma"]) if pd.notna(row["uma"]) else "",
    }


def parse_transport_ids(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        parsed = ast.literal_eval(str(value))
    except (ValueError, SyntaxError):
        return []
    if not isinstance(parsed, (list, tuple)):
        return []
    return [str(item) for item in parsed]


def build_master_index(master: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    master = master.copy()
    master["fecha_str"] = master["fecha"].dt.strftime("%Y-%m-%d")
    master["nombre_norm"] = master["nombre"].apply(norm_name)
    master["transporte_str"] = master["transporte"].astype(str)
    master["cliente"] = master["cliente"].astype("Int64")
    master = master.dropna(subset=["cliente"]).copy()
    master["cliente"] = master["cliente"].astype(int)

    by_date_name: dict[tuple[str, str], pd.DataFrame] = {}
    for key, group in master.groupby(["fecha_str", "nombre_norm"], sort=False):
        by_date_name[key] = group
    return master, by_date_name


def resolve_stop(
    date_str: str,
    entry: dict,
    by_date_name: dict[tuple[str, str], pd.DataFrame],
    geo_lookup: dict[int, tuple[float, float]],
) -> tuple[dict | None, list[dict]]:
    """Returns (stop_info, line_records) or (None, []) if unresolvable."""
    name_norm = norm_name(entry.get("client_name"))
    candidates = by_date_name.get((date_str, name_norm))
    if candidates is None or candidates.empty:
        return None, []

    transport_ids = set(parse_transport_ids(entry.get("transport_ids")))
    if transport_ids:
        narrowed = candidates[candidates["transporte_str"].isin(transport_ids)]
        if not narrowed.empty:
            candidates = narrowed

    candidates = candidates[candidates["cliente"].isin(geo_lookup.keys())]
    if candidates.empty:
        return None, []

    pallets_per_cliente = (
        candidates.groupby("cliente")["palets_ocupados"].sum().sort_values(ascending=False)
    )
    main_cliente = int(pallets_per_cliente.index[0])
    lat, lon = geo_lookup[main_cliente]

    name_value = entry.get("client_name") or candidates["nombre"].iloc[0]
    pallets_total = float(candidates["palets_ocupados"].sum())

    stop = {
        "cliente": main_cliente,
        "name": str(name_value),
        "lat": float(lat),
        "lon": float(lon),
        "pallets": round(pallets_total, 3),
        "_lines_df": candidates,
    }
    return stop, []


def build_optimized_payload(
    plan_for_date: list[list[dict]],
    date_str: str,
    by_date_name: dict[tuple[str, str], pd.DataFrame],
    geo_lookup: dict[int, tuple[float, float]],
) -> tuple[dict, list[dict]]:
    raw_clusters = []
    for trucks_idx, truck_entries in enumerate(plan_for_date):
        stops: list[dict] = []
        for entry in truck_entries:
            stop, _ = resolve_stop(date_str, entry, by_date_name, geo_lookup)
            if stop is not None:
                stops.append(stop)
        if not stops:
            continue
        ordered = nearest_neighbor_order(stops, DDI_MOLLET)
        for seq, stop in enumerate(ordered, start=1):
            stop["seq"] = seq
        distance_km = route_distance_km(ordered, DDI_MOLLET)
        time_min = distance_km / URBAN_KMH * 60
        pallets_total = sum(stop["pallets"] for stop in ordered)
        truck_size = choose_truck_size(pallets_total)
        occupation_pct = pallets_total / truck_size * 100 if truck_size else 0.0

        line_records: list[dict] = []
        for stop in ordered:
            for row in stop["_lines_df"].itertuples():
                line_records.append(line_record(pd.Series({
                    "cantidad": row.cantidad,
                    "cliente": row.cliente,
                    "material": row.material,
                    "producto": row.producto,
                    "retornable": row.retornable,
                    "palets_ocupados": row.palets_ocupados,
                    "uma": row.uma,
                }), stop["seq"]))
        load_plan = pack_pallets(line_records, truck_size)

        cluster_seed = {
            "id": str(trucks_idx + 1),
            "truck_size": int(truck_size),
            "stops_payload": [
                {
                    "seq": stop["seq"],
                    "cliente": stop["cliente"],
                    "name": stop["name"],
                    "lat": stop["lat"],
                    "lon": stop["lon"],
                    "pallets": stop["pallets"],
                }
                for stop in ordered
            ],
            "polyline": polyline_for(ordered, DDI_MOLLET),
            "distance_km": distance_km,
            "time_min": time_min,
            "occupation_pct": occupation_pct,
            "pallets": pallets_total,
            "load_plan": load_plan,
        }
        raw_clusters.append(cluster_seed)

    raw_clusters.sort(key=lambda c: c["distance_km"], reverse=True)
    clusters_payload: list[dict] = []
    for index, cluster in enumerate(raw_clusters):
        clusters_payload.append(
            {
                "id": cluster["id"],
                "truck_size": int(cluster["truck_size"]),
                "color": COLORS[index % len(COLORS)],
                "stops": cluster["stops_payload"],
                "polyline": cluster["polyline"],
                "distance_km": round(float(cluster["distance_km"]), 2),
                "time_min": round(float(cluster["time_min"]), 1),
                "occupation_pct": round(float(cluster["occupation_pct"]), 1),
                "load_plan": cluster["load_plan"],
            }
        )
    return clusters_payload, raw_clusters


def build_baseline_payload(
    date_str: str,
    master: pd.DataFrame,
    geo_lookup: dict[int, tuple[float, float]],
) -> tuple[list[dict], list[dict]]:
    day = master[master["fecha_str"] == date_str].copy()
    if day.empty:
        return [], []

    raw_clusters: list[dict] = []
    for transporte, group in day.groupby("transporte_str", sort=False):
        stops_records: list[dict] = []
        for cliente, lines in group.groupby("cliente", sort=False):
            cliente_int = int(cliente)
            if cliente_int not in geo_lookup:
                continue
            lat, lon = geo_lookup[cliente_int]
            name = lines["nombre"].dropna().iloc[0] if lines["nombre"].notna().any() else f"Client {cliente_int}"
            stops_records.append(
                {
                    "cliente": cliente_int,
                    "name": str(name),
                    "lat": float(lat),
                    "lon": float(lon),
                    "pallets": float(lines["palets_ocupados"].sum()),
                    "entrega": int(lines["entrega"].iloc[0]) if "entrega" in lines and pd.notna(lines["entrega"].iloc[0]) else 0,
                    "_lines_df": lines,
                }
            )
        if not stops_records:
            continue
        stops_records.sort(key=lambda stop: (stop["entrega"], stop["cliente"]))
        for seq, stop in enumerate(stops_records, start=1):
            stop["seq"] = seq
        distance_km = route_distance_km(stops_records, DDI_MOLLET)
        time_min = distance_km / URBAN_KMH * 60
        pallets_total = sum(stop["pallets"] for stop in stops_records)
        truck_size = choose_truck_size(pallets_total)
        occupation_pct = pallets_total / truck_size * 100 if truck_size else 0.0

        line_records: list[dict] = []
        for stop in stops_records:
            for row in stop["_lines_df"].itertuples():
                line_records.append(line_record(pd.Series({
                    "cantidad": row.cantidad,
                    "cliente": row.cliente,
                    "material": row.material,
                    "producto": row.producto,
                    "retornable": row.retornable,
                    "palets_ocupados": row.palets_ocupados,
                    "uma": row.uma,
                }), stop["seq"]))
        load_plan = pack_pallets(line_records, truck_size)

        raw_clusters.append({
            "id": str(transporte),
            "truck_size": int(truck_size),
            "stops_payload": [
                {
                    "seq": stop["seq"],
                    "cliente": stop["cliente"],
                    "name": stop["name"],
                    "lat": stop["lat"],
                    "lon": stop["lon"],
                    "pallets": round(stop["pallets"], 3),
                }
                for stop in stops_records
            ],
            "polyline": polyline_for(stops_records, DDI_MOLLET),
            "distance_km": distance_km,
            "time_min": time_min,
            "occupation_pct": occupation_pct,
            "pallets": pallets_total,
            "load_plan": load_plan,
        })

    raw_clusters.sort(key=lambda c: c["distance_km"], reverse=True)
    clusters_payload: list[dict] = []
    for index, cluster in enumerate(raw_clusters):
        clusters_payload.append({
            "id": cluster["id"],
            "truck_size": int(cluster["truck_size"]),
            "color": COLORS[index % len(COLORS)],
            "stops": cluster["stops_payload"],
            "polyline": cluster["polyline"],
            "distance_km": round(float(cluster["distance_km"]), 2),
            "time_min": round(float(cluster["time_min"]), 1),
            "occupation_pct": round(float(cluster["occupation_pct"]), 1),
            "load_plan": cluster["load_plan"],
        })
    return clusters_payload, raw_clusters


def basic_kpis(raw_clusters: list[dict]) -> dict:
    if not raw_clusters:
        return {
            "total_km": 0.0, "avg_route_km": 0.0, "avg_occupation_pct": 0.0,
            "trucks_used": 0, "total_pallets": 0.0, "total_time_min": 0.0,
        }
    total_km = sum(c["distance_km"] for c in raw_clusters)
    avg_km = total_km / len(raw_clusters)
    avg_occ = sum(c["occupation_pct"] for c in raw_clusters) / len(raw_clusters)
    total_pallets = sum(c["pallets"] for c in raw_clusters)
    total_time = sum(c["time_min"] for c in raw_clusters)
    return {
        "total_km": round(float(total_km), 1),
        "avg_route_km": round(float(avg_km), 1),
        "avg_occupation_pct": round(float(avg_occ), 1),
        "trucks_used": len(raw_clusters),
        "total_pallets": round(float(total_pallets), 1),
        "total_time_min": round(float(total_time), 1),
    }


def comparison_kpis(baseline_raw: list[dict], optimized_raw: list[dict]) -> dict:
    baseline_km = float(sum(c["distance_km"] for c in baseline_raw))
    optimized_km = float(sum(c["distance_km"] for c in optimized_raw))
    km_saved = baseline_km - optimized_km
    baseline_occ = (
        sum(c["occupation_pct"] for c in baseline_raw) / len(baseline_raw)
        if baseline_raw else 0.0
    )
    optimized_occ = (
        sum(c["occupation_pct"] for c in optimized_raw) / len(optimized_raw)
        if optimized_raw else 0.0
    )
    return {
        "baseline_km": round(baseline_km, 1),
        "optimized_km": round(optimized_km, 1),
        "km_saved": round(km_saved, 1),
        "km_saved_pct": round(km_saved / baseline_km * 100, 1) if baseline_km else 0.0,
        "baseline_avg_occupation_pct": round(float(baseline_occ), 1),
        "optimized_avg_occupation_pct": round(float(optimized_occ), 1),
        "co2_saved_kg": round(km_saved * CO2_KG_PER_KM, 1),
        "time_saved_min": round(km_saved / URBAN_KMH * 60, 1),
        "baseline_trucks": len(baseline_raw),
        "optimized_trucks": len(optimized_raw),
    }


def write_scenario(path: Path, *, date: str, label: str, clusters: list[dict], kpis: dict, n_clients: int) -> None:
    payload = {
        "metadata": {
            "date": date,
            "label": label,
            "n_transports": len(clusters),
            "n_clients": n_clients,
        },
        "depot": DDI_MOLLET,
        "clusters": clusters,
        "kpis": kpis,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def label_for(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d, %Y")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not FFD_FILE.exists():
        raise FileNotFoundError(f"Missing {FFD_FILE}")
    if not MASTER_FILE.exists() or not GEOCODED_FILE.exists():
        raise FileNotFoundError("master.parquet or geocoded.parquet not found in outputs/")

    plan: dict[str, list[list[dict]]] = json.loads(FFD_FILE.read_text(encoding="utf-8"))
    master = pd.read_parquet(MASTER_FILE)
    geocoded = pd.read_parquet(GEOCODED_FILE).dropna(subset=["lat", "lon", "cliente"])
    geocoded["cliente"] = geocoded["cliente"].astype(int)
    geo_lookup = {
        int(row.cliente): (float(row.lat), float(row.lon))
        for row in geocoded.itertuples()
    }

    master, by_date_name = build_master_index(master)

    manifest_dates: list[dict] = []
    skipped: list[str] = []

    for date_str in sorted(plan.keys()):
        plan_for_date = plan[date_str]

        opt_clusters, opt_raw = build_optimized_payload(plan_for_date, date_str, by_date_name, geo_lookup)
        base_clusters, base_raw = build_baseline_payload(date_str, master, geo_lookup)

        if not opt_clusters or not base_clusters:
            skipped.append(date_str)
            continue

        opt_kpis = {**basic_kpis(opt_raw), **comparison_kpis(base_raw, opt_raw)}
        base_kpis = basic_kpis(base_raw)

        opt_clients = len({stop["cliente"] for c in opt_clusters for stop in c["stops"]})
        base_clients = len({stop["cliente"] for c in base_clusters for stop in c["stops"]})

        safe_date = date_str.replace("-", "")
        baseline_path = OUT / f"scenario_{safe_date}_baseline.json"
        optimized_path = OUT / f"scenario_{safe_date}_optimized.json"

        write_scenario(baseline_path, date=date_str, label="baseline", clusters=base_clusters, kpis=base_kpis, n_clients=base_clients)
        write_scenario(optimized_path, date=date_str, label="optimized", clusters=opt_clusters, kpis=opt_kpis, n_clients=opt_clients)

        manifest_dates.append({
            "date": date_str,
            "label": label_for(date_str),
            "baseline": baseline_path.name,
            "optimized": optimized_path.name,
        })
        print(
            f"  {date_str}: baseline {len(base_clusters):>3} routes / {opt_kpis['baseline_km']:>6.1f} km"
            f"  ->  optimized {len(opt_clusters):>2} routes / {opt_kpis['optimized_km']:>6.1f} km"
            f"  (-{opt_kpis['km_saved_pct']:.1f}%)"
        )

    default_date = DEFAULT_DATE if any(d["date"] == DEFAULT_DATE for d in manifest_dates) else manifest_dates[0]["date"]
    manifest = {"defaultDate": default_date, "dates": manifest_dates}
    (OUT / "scenario_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Wrote {len(manifest_dates)} scenario days to {OUT}")
    if skipped:
        print(f"Skipped (no resolvable data): {', '.join(skipped)}")


if __name__ == "__main__":
    main()
