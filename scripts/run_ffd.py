from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from damm_logistics.packing.ffd import FleetSpec, assign_orders_ffd  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration -- edit these variables directly
# ---------------------------------------------------------------------------

DAILY_ITEMS_PATH = REPO_ROOT / "notebooks/daily_data/daily_client_items.csv"
DAILY_ORDERS_PATH = REPO_ROOT / "notebooks/daily_data/daily_client_orders.csv"
OUTPUT_DIR = REPO_ROOT / "data/custom/ffd"

CLUSTER_SOURCE = "normalized"
CLUSTER_PENALTY = 1.0

WEIGHT_COL = "pallet_equiv"
CLIENT_COL = "client_name"
ORDER_ID_COL = None

FLEET_SPECS = [
    FleetSpec(truck_type="van", count=1, capacity=3),
    FleetSpec(truck_type="standard", count=11, capacity=6),
    FleetSpec(truck_type="large", count=4, capacity=8),
]

PALLET_FRACTIONS: dict[str, float] = {
    "caj": 1 / 60,
    "brl": 1 / 20,
    "bot": 1 / 500,
    "un": 1 / 500,
    "pak": 1 / 60,
    "tb": 1 / 30,
    "est": 1 / 60,
    "zpr": 1 / 500,
    "pq": 1 / 60,
    "tir": 1 / 60,
    "bid": 1 / 20,
}
DEFAULT_PALLET_FRACTION = 1 / 60

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_pallet_equivalents(items_df: pd.DataFrame) -> pd.DataFrame:
    df = items_df.copy()
    df["unit_clean"] = df["unit"].astype(str).str.strip().str.lower()
    df["pallet_fraction"] = df["unit_clean"].map(PALLET_FRACTIONS).fillna(DEFAULT_PALLET_FRACTION)
    df["pallet_equiv"] = df["total_quantity"] * df["pallet_fraction"]
    return df


def aggregate_client_orders(items_df: pd.DataFrame, date_col: str = "order_date") -> pd.DataFrame:
    return (
        items_df.groupby([date_col, CLIENT_COL], as_index=False)
        .agg(
            pallet_equiv=(WEIGHT_COL, "sum"),
            total_lines=("material", "count"),
            total_items=("total_quantity", "sum"),
        )
    )


def build_truck_plan(
    day_orders_df: pd.DataFrame,
    daily_orders_detail_df: pd.DataFrame,
    date: str,
) -> list[list[dict]]:
    result = assign_orders_ffd(
        day_orders_df,
        fleet_specs=FLEET_SPECS,
        cluster_penalty=CLUSTER_PENALTY,
        cluster_source=CLUSTER_SOURCE,
        weight_col=WEIGHT_COL,
        client_col=CLIENT_COL,
        order_id_col=ORDER_ID_COL,
    )

    order_id_to_client = dict(zip(day_orders_df.index, day_orders_df[CLIENT_COL]))

    day_detail = daily_orders_detail_df[
        daily_orders_detail_df["order_date"] == date
    ].copy()
    detail_lookup: dict[str, dict] = {}
    for _, row in day_detail.iterrows():
        detail_lookup[row["client_name"]] = {
            "client_name": row["client_name"],
            "transport_ids": row.get("transport_ids", ""),
            "total_lines": int(row.get("total_lines", 0)),
            "total_quantity": int(row.get("total_quantity", 0)),
            "ordered_items": row.get("ordered_items", ""),
        }

    trucks: list[list[dict]] = []
    if result.assignments.empty:
        return trucks

    for truck_id in sorted(result.assignments["truck_id"].unique()):
        truck_assignments = result.assignments[result.assignments["truck_id"] == truck_id]
        truck_clients: list[dict] = []
        seen_clients: set[str] = set()

        for _, assignment in truck_assignments.iterrows():
            raw_order_id = assignment["order_id"]
            order_idx = int(str(raw_order_id).split("_split")[0])
            client = order_id_to_client.get(order_idx, "UNKNOWN")

            if client in seen_clients:
                continue
            seen_clients.add(client)

            client_detail = detail_lookup.get(client, {"client_name": client})
            client_entry = dict(client_detail)
            client_entry["pallet_equiv"] = float(
                day_orders_df.loc[
                    day_orders_df[CLIENT_COL] == client, WEIGHT_COL
                ].sum()
            )
            truck_clients.append(client_entry)

        trucks.append(truck_clients)

    return trucks


def main() -> int:
    if not DAILY_ITEMS_PATH.exists():
        raise FileNotFoundError(f"Missing daily items CSV: {DAILY_ITEMS_PATH}")
    if not DAILY_ORDERS_PATH.exists():
        raise FileNotFoundError(f"Missing daily orders CSV: {DAILY_ORDERS_PATH}")

    raw_items_df = pd.read_csv(DAILY_ITEMS_PATH)
    items_df = compute_pallet_equivalents(raw_items_df)
    client_orders_df = aggregate_client_orders(items_df)

    daily_orders_detail_df = pd.read_csv(DAILY_ORDERS_PATH)

    dates = sorted(client_orders_df["order_date"].dropna().unique())

    truck_plan: dict[str, list[list[dict]]] = {}

    for date in dates:
        day_orders_df = client_orders_df[client_orders_df["order_date"] == date].copy()

        print(f"Date: {date}")
        print(f"  Client orders: {len(day_orders_df)}")
        print(f"  Total pallet-equivalents: {day_orders_df[WEIGHT_COL].sum():.2f}")

        trucks = build_truck_plan(day_orders_df, daily_orders_detail_df, date)
        truck_plan[date] = trucks

        print(f"  Trucks used: {len(trucks)}")
        for i, truck in enumerate(trucks):
            clients = [c["client_name"] for c in truck]
            total_pallets = sum(c.get("pallet_equiv", 0) for c in truck)
            print(f"    Truck {i}: {len(clients)} clients, {total_pallets:.2f} pallets")
            for c in clients:
                print(f"      - {c}")
        print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"truck_plan_{CLUSTER_SOURCE}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(truck_plan, f, ensure_ascii=False, indent=2)

    print(f"Truck plan written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
