"""
Data contracts shared between the cluster/route teammate, the packer, the
copilot, and the frontend. Stable schema — change with care.

Two entry shapes:

1. RouteRequest: what the cluster teammate produces (ordered stops with the
   merchandise per stop). The packer consumes this.
2. LoadPlan: what the packer produces. The frontend renders it. The copilot
   exposes it as tools.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ----- Inputs (route + cargo per stop) -----


class Line(BaseModel):
    material: str = Field(..., description="SKU code, e.g. ED13")
    name: str
    qty: int
    umv: Literal[
        "CAJ", "UN", "BOT", "BRL", "TB", "PAK", "EST", "PQ", "TIR", "BID", "ZPR"
    ] = "CAJ"
    family: str | None = Field(None, description="ZM040 first-4-char family code, e.g. 00CZ")
    warehouse_loc: str = Field("ZCG", description="Picking location like AA09A1, ZCG, ENVASE")
    is_returnable: bool = False
    fragile: bool = False
    cases_equiv: float = Field(
        1.0,
        description=(
            "Volumetric size in 'standard case' units. A 30L barrel ~= 4 cases "
            "(mentor rule of thumb)."
        ),
    )


class Delivery(BaseModel):
    delivery_id: str = Field(..., description="Albaran number, e.g. 827937019")
    lines: list[Line]


class TimeWindow(BaseModel):
    start: str = Field(..., description="HH:MM")
    end: str


class Stop(BaseModel):
    order: int = Field(..., ge=1, description="1-based visit order in the route")
    client_id: str
    client_name: str
    address: str = ""
    lat: float | None = None
    lon: float | None = None
    zone: str | None = None
    cluster_id: str | None = Field(
        None,
        description=(
            "Park-and-walk cluster id. Stops sharing this id get parked at once."
        ),
    )
    interior_distance_m: float = Field(
        0.0,
        description=(
            "Walking distance inside the customer's premises from truck to drop "
            "point. Mentor flagged this as the real unload-time driver."
        ),
    )
    time_windows: list[TimeWindow] = []
    deliveries: list[Delivery]


class Driver(BaseModel):
    id: str
    name: str
    license_level: Literal[1, 2, 3] = 3


class Truck(BaseModel):
    id: str
    plate: str | None = None
    pallet_slots: int = Field(..., description="Floor pallet positions (3, 6, or 8)")
    levels_per_pallet: int = Field(4, description="Vertical levels of cases per pallet")
    max_cases: int = Field(..., description="Hard ceiling on total cases on board")
    lateral_access: bool = True


class RouteRequest(BaseModel):
    transport_id: str
    route_code: str
    date: str
    driver: Driver
    truck: Truck
    stops: list[Stop]


# ----- Outputs (load plan) -----


class Cell(BaseModel):
    slot_x: int = Field(..., description="Pallet position along the truck length, 0-based")
    level: int = Field(..., ge=0, description="0 = floor, increases upward")
    stop_order: int
    client_id: str
    client_name: str
    material: str
    material_name: str
    cases: int
    is_returnable: bool = False
    fragile: bool = False
    color_hex: str = Field("#999999", description="Per-stop color for the 3D view")


class Action(BaseModel):
    type: Literal["unload", "load_returnable", "shuffle"]
    slot_x: int
    level: int
    material: str
    cases: int
    note: str | None = None


class TimelineFrame(BaseModel):
    stop_order: int
    client_id: str
    client_name: str
    actions: list[Action]
    cells_after: list[Cell]
    alerts: list[str] = []


class Alert(BaseModel):
    severity: Literal["info", "warn", "block"]
    code: str
    message: str
    stop_order: int | None = None


class Metrics(BaseModel):
    total_cases: int
    pallets_used: int
    capacity_utilization: float
    whole_pallet_stops: int
    fragile_under_heavy_violations: int
    park_and_walk_clusters: int
    estimated_handling_cost: float
    estimated_total_minutes: float


class LoadPlan(BaseModel):
    transport_id: str
    route_code: str
    date: str
    driver: Driver
    truck: Truck
    stops: list[Stop]
    cells_initial: list[Cell] = Field(
        ..., description="State of the truck at warehouse departure"
    )
    timeline: list[TimelineFrame]
    alerts: list[Alert] = []
    metrics: Metrics


# ----- Copilot tool I/O -----


class WhatIfRequest(BaseModel):
    swap_stop_a: int = Field(..., description="1-based order of first stop to swap")
    swap_stop_b: int = Field(..., description="1-based order of second stop to swap")


class WhatIfResponse(BaseModel):
    feasible: bool
    delta_metrics: dict
    blocking_alerts: list[Alert]
