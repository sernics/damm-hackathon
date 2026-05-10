"""Customer-level profile builder.

Output: one row per `client_id` with the operational features the selection
algorithm and the briefing LLM both consume.
"""

from __future__ import annotations

import pandas as pd

from veteran_capture.logging_setup import get_logger
from veteran_capture.mining.sku import cases_equiv, family_from_name, is_returnable

logger = get_logger(__name__)

PROFILE_COLUMNS: tuple[str, ...] = (
    "client_id",
    "client_name",
    "trade_name",
    "calle",
    "cp",
    "poblacion",
    "town_norm",
    "zone_code",
    "client_kind",
    "n_deliveries",
    "n_lines",
    "n_distinct_skus",
    "n_active_dates",
    "first_delivery_date",
    "last_delivery_date",
    "delivery_frequency_days",
    "total_cases_equiv",
    "mean_cases_per_delivery",
    "max_cases_per_delivery",
    "pct_returnable_lines",
    "pct_returnable_volume",
    "has_schedule",
    "top_family",
    "top_skus",
    "drivers_seen",
)


def _classify_client(client_id: str) -> str:
    """Empirical: 10-digit -> individual, 6-digit -> chain, anything else -> unknown."""
    if not isinstance(client_id, str):
        return "unknown"
    if client_id.isdigit() and len(client_id) == 10 and client_id.startswith("91"):
        return "individual"
    if client_id.isdigit() and len(client_id) == 6:
        return "chain"
    return "unknown"


def _safe_div(numer: float, denom: float) -> float:
    return float(numer) / float(denom) if denom else 0.0


def _frequency_days(active_dates: pd.Series) -> float:
    """Mean number of days between two consecutive active delivery dates."""
    sorted_dates = active_dates.dropna().drop_duplicates().sort_values()
    if len(sorted_dates) < 2:
        return 0.0
    diffs = sorted_dates.diff().dropna().dt.days
    return float(diffs.mean())


def build_customer_profiles(
    detalle: pd.DataFrame,
    direcciones: pd.DataFrame,
    horarios: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate Detalle into a per-client profile, joined with master data."""
    if detalle.empty:
        logger.warning("detalle is empty; returning an empty profile frame")
        return pd.DataFrame(columns=list(PROFILE_COLUMNS))

    df = detalle.copy()
    df["cases_equiv"] = [
        cases_equiv(qty, umv) for qty, umv in zip(df["cantidad"], df["umv"], strict=False)
    ]
    df["is_returnable"] = df["material"].map(is_returnable)
    df["family"] = df["denominacion"].map(family_from_name)

    grouped = df.groupby("client_id", sort=False)

    base = grouped.agg(
        n_deliveries=("entrega", "nunique"),
        n_lines=("material", "size"),
        n_distinct_skus=("material", "nunique"),
        first_delivery_date=("fecha", "min"),
        last_delivery_date=("fecha", "max"),
        n_active_dates=("fecha", lambda s: s.dropna().dt.normalize().nunique()),
        total_cases_equiv=("cases_equiv", "sum"),
        max_cases_per_delivery=("cases_equiv", "max"),
        zone_code=("zone_code", "first"),
        driver_set=("repartidor", lambda s: sorted(set(s.dropna()))),
    ).reset_index()

    # Returnable share
    ret_lines = (
        df.groupby("client_id")["is_returnable"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "ret_lines", "count": "all_lines"})
    )
    ret_volume = (
        df.assign(
            volume_ret=lambda d: d["cases_equiv"].where(d["is_returnable"], 0.0),
            volume_all=lambda d: d["cases_equiv"],
        )
        .groupby("client_id")[["volume_ret", "volume_all"]]
        .sum()
    )
    base = base.merge(ret_lines, on="client_id", how="left").merge(
        ret_volume, on="client_id", how="left"
    )
    base["pct_returnable_lines"] = base.apply(
        lambda r: _safe_div(r["ret_lines"], r["all_lines"]), axis=1
    )
    base["pct_returnable_volume"] = base.apply(
        lambda r: _safe_div(r["volume_ret"], r["volume_all"]), axis=1
    )
    base = base.drop(columns=["ret_lines", "all_lines", "volume_ret", "volume_all"])

    # Frequency between deliveries
    freq = (
        df.groupby("client_id")["fecha"].apply(_frequency_days).rename("delivery_frequency_days")
    )
    base = base.merge(freq, on="client_id", how="left")

    # Mean cases per delivery
    base["mean_cases_per_delivery"] = base.apply(
        lambda r: _safe_div(r["total_cases_equiv"], r["n_deliveries"]),
        axis=1,
    )

    # Top family + top 3 SKUs by line frequency
    top_family = df.dropna(subset=["family"]).groupby(["client_id", "family"]).size()
    top_family_df = (
        top_family.reset_index(name="n")
        .sort_values(["client_id", "n"], ascending=[True, False])
        .drop_duplicates("client_id")
        .rename(columns={"family": "top_family"})[["client_id", "top_family"]]
    )
    base = base.merge(top_family_df, on="client_id", how="left")

    top_skus_df = (
        df.groupby(["client_id", "material"])
        .size()
        .reset_index(name="n")
        .sort_values(["client_id", "n"], ascending=[True, False])
        .groupby("client_id")["material"]
        .apply(lambda s: list(s.head(3)))
        .reset_index()
        .rename(columns={"material": "top_skus"})
    )
    base = base.merge(top_skus_df, on="client_id", how="left")
    base["top_skus"] = base["top_skus"].apply(lambda v: v if isinstance(v, list) else [])

    # Names and address from direcciones (deduped master) - fallback to detalle if missing.
    direcc = direcciones[
        ["client_id", "client_name_1", "client_name_2", "calle", "cp", "poblacion", "town_norm"]
    ].drop_duplicates(subset=["client_id"])
    base = base.merge(direcc, on="client_id", how="left", suffixes=("", "_dir"))
    fallback = (
        df.groupby("client_id", sort=False)
        .agg(
            client_name_1_fb=("client_name_1", "first"),
            client_name_2_fb=("client_name_2", "first"),
            calle_fb=("calle", "first"),
            cp_fb=("cp", "first"),
            poblacion_fb=("poblacion", "first"),
            town_norm_fb=("town_norm", "first"),
        )
        .reset_index()
    )
    base = base.merge(fallback, on="client_id", how="left")
    for primary, fb in (
        ("client_name_1", "client_name_1_fb"),
        ("client_name_2", "client_name_2_fb"),
        ("calle", "calle_fb"),
        ("cp", "cp_fb"),
        ("poblacion", "poblacion_fb"),
        ("town_norm", "town_norm_fb"),
    ):
        if primary not in base.columns:
            base[primary] = base[fb]
        else:
            base[primary] = base[primary].where(base[primary].astype(bool), base[fb])
    base = base.drop(columns=[c for c in base.columns if c.endswith("_fb")])

    base["client_name"] = base["client_name_1"].fillna(base["client_id"])
    base["trade_name"] = base["client_name_2"].fillna(base["client_name_1"])

    # Schedule presence
    has_sched = horarios.assign(_has=True)[["client_id", "_has"]].drop_duplicates("client_id")
    base = base.merge(has_sched, on="client_id", how="left")
    base["has_schedule"] = base["_has"].fillna(False).astype(bool)
    base = base.drop(columns=["_has"])

    base["client_kind"] = base["client_id"].map(_classify_client)
    base = base.rename(columns={"driver_set": "drivers_seen"})

    # Final column order, only keep what's documented.
    out = base[list(PROFILE_COLUMNS)].copy()
    logger.info(
        "built customer profiles",
        extra={
            "clients": len(out),
            "with_returnables": int((out["pct_returnable_lines"] > 0).sum()),
            "chains": int((out["client_kind"] == "chain").sum()),
            "with_schedule": int(out["has_schedule"].sum()),
        },
    )
    return out
