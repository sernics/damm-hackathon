from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from damm_logistics.clustering.loaders import load_cluster_lookup


@dataclass
class Truck:
    truck_id: int
    capacity: float
    remaining_capacity: float
    truck_type: str = "truck"
    cluster_ids: set[Any] = field(default_factory=set)
    order_ids: list[Any] = field(default_factory=list)
    total_weight: float = 0.0


@dataclass(frozen=True)
class FleetSpec:
    truck_type: str
    count: int
    capacity: float


@dataclass(frozen=True)
class FFDResult:
    assignments: pd.DataFrame
    trucks: pd.DataFrame
    unassigned: pd.DataFrame
    metrics: dict[str, float | int]


def prepare_orders(
    orders_df: pd.DataFrame,
    weight_col: str,
    client_col: str,
    order_id_col: str | None = None,
) -> pd.DataFrame:
    required_columns = {weight_col, client_col}
    if order_id_col is not None:
        required_columns.add(order_id_col)

    missing_columns = required_columns - set(orders_df.columns)
    if missing_columns:
        raise ValueError(f"Missing columns in orders dataframe: {sorted(missing_columns)}")

    prepared_df = orders_df.copy()
    prepared_df[weight_col] = pd.to_numeric(prepared_df[weight_col], errors="coerce")
    prepared_df[client_col] = prepared_df[client_col].astype(str).str.strip()

    if order_id_col is None:
        prepared_df = prepared_df.reset_index(drop=False).rename(columns={"index": "order_id"})
    else:
        prepared_df["order_id"] = prepared_df[order_id_col]

    prepared_df = prepared_df[prepared_df[client_col] != ""].copy()
    return prepared_df


def join_cluster_lookup(
    orders_df: pd.DataFrame,
    cluster_lookup_df: pd.DataFrame,
    client_col: str,
) -> pd.DataFrame:
    required_columns = {"client_name", "cluster_id", "cluster_size"}
    missing_columns = required_columns - set(cluster_lookup_df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing columns in cluster lookup dataframe: {sorted(missing_columns)}"
        )

    lookup_df = cluster_lookup_df.copy()
    lookup_df["client_name"] = lookup_df["client_name"].astype(str).str.strip()
    lookup_df = lookup_df.drop_duplicates(subset=["client_name"], keep="first")

    clustered_orders_df = orders_df.merge(
        lookup_df[["client_name", "cluster_id", "cluster_size"]],
        left_on=client_col,
        right_on="client_name",
        how="left",
    )
    return clustered_orders_df.drop(columns=["client_name"])


def _cluster_key(value: Any) -> Any:
    if pd.isna(value):
        return "__UNKNOWN_CLUSTER__"
    return value


def score_truck(
    truck: Truck,
    order: Mapping[str, Any],
    cluster_penalty: float,
    weight_col: str = "weight",
    cluster_col: str = "cluster_id",
) -> float | None:
    order_weight = float(order[weight_col])
    remaining_after_assignment = truck.remaining_capacity - order_weight
    if remaining_after_assignment < 0:
        return None

    cluster_id = _cluster_key(order.get(cluster_col))
    penalty = 0.0 if cluster_id in truck.cluster_ids else cluster_penalty
    return remaining_after_assignment + penalty


def _add_order_to_truck(
    truck: Truck,
    order: Mapping[str, Any],
    weight_col: str,
    cluster_col: str,
) -> None:
    order_weight = float(order[weight_col])
    truck.remaining_capacity -= order_weight
    truck.total_weight += order_weight
    truck.order_ids.append(order["order_id"])
    truck.cluster_ids.add(_cluster_key(order.get(cluster_col)))


def _build_trucks_df(trucks: list[Truck]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "truck_id": truck.truck_id,
                "truck_type": truck.truck_type,
                "capacity": truck.capacity,
                "total_weight": truck.total_weight,
                "remaining_capacity": truck.remaining_capacity,
                "utilization": truck.total_weight / truck.capacity if truck.capacity else 0.0,
                "order_count": len(truck.order_ids),
                "distinct_clusters": len(truck.cluster_ids),
                "cluster_ids": sorted(str(cluster_id) for cluster_id in truck.cluster_ids),
            }
            for truck in trucks
        ]
    )


def summarize_truck_plan(
    assignments_df: pd.DataFrame,
    trucks_df: pd.DataFrame,
    weight_col: str = "assignment_weight",
    truck_col: str = "truck_id",
    cluster_col: str = "cluster_id",
    unassigned_count: int = 0,
) -> dict[str, float | int]:
    if assignments_df.empty:
        return {
            "truck_count": 0,
            "assigned_orders": 0,
            "unassigned_orders": unassigned_count,
            "total_weight": 0.0,
            "total_capacity": 0.0,
            "average_utilization": 0.0,
            "min_utilization": 0.0,
            "max_utilization": 0.0,
            "fleet_utilization": 0.0,
            "mixed_cluster_trucks": 0,
            "average_distinct_clusters_per_truck": 0.0,
        }

    utilization = trucks_df["utilization"] if not trucks_df.empty else pd.Series(dtype=float)
    cluster_counts = assignments_df.groupby(truck_col)[cluster_col].nunique(dropna=False)
    total_weight = float(assignments_df[weight_col].sum())
    total_capacity = float(trucks_df["capacity"].sum()) if not trucks_df.empty else 0.0

    return {
        "truck_count": int(assignments_df[truck_col].nunique()),
        "assigned_orders": int(len(assignments_df)),
        "unassigned_orders": int(unassigned_count),
        "total_weight": total_weight,
        "total_capacity": total_capacity,
        "average_utilization": float(utilization.mean()),
        "min_utilization": float(utilization.min()),
        "max_utilization": float(utilization.max()),
        "fleet_utilization": total_weight / total_capacity if total_capacity else 0.0,
        "mixed_cluster_trucks": int((cluster_counts > 1).sum()),
        "average_distinct_clusters_per_truck": float(cluster_counts.mean()),
    }


def build_fleet(fleet_specs: list[FleetSpec]) -> list[Truck]:
    trucks: list[Truck] = []
    for spec in fleet_specs:
        if spec.count < 0:
            raise ValueError(f"Truck count cannot be negative: {spec}")
        if spec.capacity <= 0:
            raise ValueError(f"Truck capacity must be positive: {spec}")

        for _ in range(spec.count):
            trucks.append(
                Truck(
                    truck_id=len(trucks),
                    truck_type=spec.truck_type,
                    capacity=float(spec.capacity),
                    remaining_capacity=float(spec.capacity),
                )
            )
    return trucks


def assign_orders_ffd(
    orders_df: pd.DataFrame,
    cluster_penalty: float,
    cluster_source: str | None = None,
    *,
    fleet_specs: list[FleetSpec] | None = None,
    truck_capacity: float | None = None,
    cluster_lookup_df: pd.DataFrame | None = None,
    cluster_root: Path | None = None,
    weight_col: str = "converted_amount",
    client_col: str = "client",
    order_id_col: str | None = None,
    cluster_col: str = "cluster_id",
) -> FFDResult:
    unlimited_truck_capacity: float | None = None
    if fleet_specs is None:
        if truck_capacity is None:
            raise ValueError("Provide either fleet_specs or truck_capacity.")
        if truck_capacity <= 0:
            raise ValueError("truck_capacity must be positive.")
        unlimited_truck_capacity = float(truck_capacity)
    if cluster_penalty < 0:
        raise ValueError("cluster_penalty cannot be negative.")

    prepared_orders_df = prepare_orders(
        orders_df=orders_df,
        weight_col=weight_col,
        client_col=client_col,
        order_id_col=order_id_col,
    )

    if cluster_lookup_df is None and cluster_source is not None:
        cluster_lookup_df = load_cluster_lookup(cluster_source, cluster_root=cluster_root)

    if cluster_lookup_df is not None:
        prepared_orders_df = join_cluster_lookup(
            prepared_orders_df,
            cluster_lookup_df=cluster_lookup_df,
            client_col=client_col,
        )
    elif cluster_col not in prepared_orders_df.columns:
        prepared_orders_df[cluster_col] = pd.NA

    invalid_weight_mask = (
        prepared_orders_df[weight_col].isna() | (prepared_orders_df[weight_col] <= 0)
    )
    invalid_orders_df = prepared_orders_df[invalid_weight_mask].copy()
    valid_orders_df = prepared_orders_df[~invalid_weight_mask].copy()

    sorted_orders_df = valid_orders_df.sort_values(
        [weight_col, "order_id"], ascending=[False, True]
    ).reset_index(drop=True)

    available_trucks = build_fleet(fleet_specs) if fleet_specs is not None else []
    if fleet_specs is not None and not available_trucks:
        raise ValueError("fleet_specs must include at least one truck.")

    opened_trucks: list[Truck] = []
    assignment_rows: list[dict[str, Any]] = []
    unassigned_rows: list[dict[str, Any]] = [
        {**row, "unassigned_reason": "missing_or_non_positive_weight"}
        for row in invalid_orders_df.to_dict("records")
    ]
    max_single_truck_capacity = (
        max(truck.capacity for truck in available_trucks)
        if fleet_specs is not None
        else float(unlimited_truck_capacity)
    )

    def _assign_single_order(
        order: dict[str, Any],
        order_weight: float,
    ) -> None:
        """Try to assign a single order (or partial split) to a truck."""
        valid_scores = [
            (
                score_truck(
                    truck,
                    order,
                    cluster_penalty=cluster_penalty,
                    weight_col=weight_col,
                    cluster_col=cluster_col,
                ),
                truck,
            )
            for truck in opened_trucks
        ]
        valid_scores = [(s, t) for s, t in valid_scores if s is not None]

        selected_truck: Truck | None = None
        if valid_scores:
            _, selected_truck = min(valid_scores, key=lambda item: (item[0], item[1].truck_id))
        elif fleet_specs is not None:
            available_candidates = [
                truck for truck in available_trucks if truck.remaining_capacity >= order_weight
            ]
            if available_candidates:
                selected_truck = min(
                    available_candidates,
                    key=lambda truck: (truck.capacity, truck.truck_id),
                )
                available_trucks.remove(selected_truck)
                opened_trucks.append(selected_truck)
        else:
            selected_truck = Truck(
                truck_id=len(opened_trucks),
                truck_type="truck",
                capacity=float(unlimited_truck_capacity),
                remaining_capacity=float(unlimited_truck_capacity),
            )
            opened_trucks.append(selected_truck)

        if selected_truck is None:
            unassigned = dict(order)
            unassigned["unassigned_reason"] = "fleet_capacity_exhausted"
            unassigned_rows.append(unassigned)
            return

        _add_order_to_truck(
            selected_truck,
            order,
            weight_col=weight_col,
            cluster_col=cluster_col,
        )

        assignment = dict(order)
        assignment["truck_id"] = selected_truck.truck_id
        assignment["assignment_weight"] = order_weight
        assignment["remaining_capacity_after_assignment"] = selected_truck.remaining_capacity
        assignment_rows.append(assignment)

    for order in sorted_orders_df.to_dict("records"):
        order_weight = float(order[weight_col])

        if order_weight <= max_single_truck_capacity:
            _assign_single_order(order, order_weight)
            continue

        remaining = order_weight
        split_idx = 0
        while remaining > 0:
            chunk = min(remaining, max_single_truck_capacity)
            split_order = dict(order)
            split_order[weight_col] = chunk
            split_order["order_id"] = f"{order['order_id']}_split{split_idx}"
            _assign_single_order(split_order, chunk)
            remaining -= chunk
            split_idx += 1

    assignments_df = pd.DataFrame(assignment_rows)
    trucks_df = _build_trucks_df(opened_trucks)
    unassigned_df = pd.DataFrame(unassigned_rows)
    metrics = summarize_truck_plan(
        assignments_df,
        trucks_df=trucks_df,
        unassigned_count=len(unassigned_df),
    )
    if fleet_specs is not None:
        fleet_truck_count = sum(spec.count for spec in fleet_specs)
        full_fleet_capacity = sum(spec.count * spec.capacity for spec in fleet_specs)
        total_weight = float(metrics["total_weight"])
        metrics.update(
            {
                "fleet_truck_count": int(fleet_truck_count),
                "unused_trucks": int(fleet_truck_count - len(opened_trucks)),
                "full_fleet_capacity": float(full_fleet_capacity),
                "full_fleet_utilization": (
                    total_weight / full_fleet_capacity if full_fleet_capacity else 0.0
                ),
            }
        )

    return FFDResult(
        assignments=assignments_df,
        trucks=trucks_df,
        unassigned=unassigned_df,
        metrics=metrics,
    )

