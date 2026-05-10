"""(Driver, customer) affinity matrix.

Used by the selection algorithm to ask the right driver about a given customer:
the more deliveries a driver has historically made to a customer, the higher
their authority on tacit operational knowledge for that customer.
"""

from __future__ import annotations

import pandas as pd

from veteran_capture.logging_setup import get_logger
from veteran_capture.mining.sku import cases_equiv as _cases_equiv

logger = get_logger(__name__)

AFFINITY_COLUMNS: tuple[str, ...] = (
    "driver_id",
    "client_id",
    "n_deliveries",
    "n_lines",
    "first_delivery_date",
    "last_delivery_date",
    "total_cases_equiv",
)


def build_driver_customer_affinity(detalle: pd.DataFrame) -> pd.DataFrame:
    """One row per (driver, customer) pair with summary stats.

    `detalle` is the frame returned by `mining.io.load_detalle`. The function
    expects `cases_equiv` to already be on the frame (added by the customer
    profile builder) and falls back to a recomputation if missing.
    """
    if detalle.empty:
        logger.warning("detalle empty; affinity frame is empty")
        return pd.DataFrame(columns=list(AFFINITY_COLUMNS))

    df = detalle.copy()
    if "cases_equiv" not in df.columns:
        df["cases_equiv"] = [
            _cases_equiv(qty, umv)
            for qty, umv in zip(df["cantidad"], df["umv"], strict=False)
        ]

    df = df.rename(columns={"repartidor": "driver_id"})
    grouped = df.groupby(["driver_id", "client_id"], sort=False)
    out = grouped.agg(
        n_deliveries=("entrega", "nunique"),
        n_lines=("material", "size"),
        first_delivery_date=("fecha", "min"),
        last_delivery_date=("fecha", "max"),
        total_cases_equiv=("cases_equiv", "sum"),
    ).reset_index()
    logger.info(
        "built driver-customer affinity",
        extra={
            "rows": len(out),
            "drivers": out["driver_id"].nunique(),
            "clients": out["client_id"].nunique(),
        },
    )
    return out[list(AFFINITY_COLUMNS)]
