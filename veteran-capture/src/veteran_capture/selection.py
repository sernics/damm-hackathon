"""Selection algorithm: which (client, driver) pair do we ask next?

The cron uses this to feed the capture flow. The goal is to maximise the
*operational value of every audio tip we receive*, given that drivers will
ignore us if we ask too often.

Scoring intuition (each factor in [0, 1] after normalisation, then combined):

- volume_score      : impact. Big-volume customers create the most value when
                      a tip is captured, because their tips will be reused on
                      many future deliveries.
- gap_score         : information gain. Clients with zero or few existing tips
                      score higher than clients we already know well.
- staleness_score   : freshness. Notes older than ~6 months prompt a refresh.
- familiarity_score : authority. The driver who has historically covered this
                      client the most knows them best — ask them.
- recency_score     : actionability. If the client has not been delivered to
                      recently, the tip risks being out of date when we capture
                      it. Slight penalty.
- complexity_bonus  : operational difficulty bumps. Customers with high
                      returnable share or with retornable barrels (mentor-flagged
                      as the trickiest part of the day) score higher because
                      tribal knowledge matters more for them.

The Damm context informs the bonus: returnable barrels (BRL30V, BRL20V) and
returnable glass crates (CJ13, CJ15) require specific handling at unload —
exactly the kind of detail we want a veteran to record.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from veteran_capture.config import get_settings
from veteran_capture.exceptions import DataNotFoundError
from veteran_capture.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ScoringWeights:
    """Tunable weights for the priority score.

    Defaults are chosen so that, when no notes exist yet (the cold-start case),
    volume + familiarity dominate. As notes accumulate, gap_score takes over.
    """

    volume: float = 0.30
    gap: float = 0.30
    staleness: float = 0.10
    familiarity: float = 0.20
    recency: float = 0.05
    complexity: float = 0.05

    def total(self) -> float:
        return (
            self.volume
            + self.gap
            + self.staleness
            + self.familiarity
            + self.recency
            + self.complexity
        )


# Public column contract emitted to the queue parquet.
QUEUE_COLUMNS: tuple[str, ...] = (
    "client_id",
    "client_name",
    "driver_id",
    "score",
    "score_volume",
    "score_gap",
    "score_staleness",
    "score_familiarity",
    "score_recency",
    "score_complexity",
    "reason",
    "n_existing_tips",
    "n_deliveries_driver_to_client",
    "client_total_cases",
    "client_pct_returnable",
    "client_last_delivery",
)


# ---------- per-factor scores (each in [0, 1]) ----------


def _volume_score(total_cases: float, max_cases_in_dataset: float) -> float:
    """Log-scale the customer's total volume into [0, 1]."""
    if max_cases_in_dataset <= 0 or total_cases <= 0:
        return 0.0
    return math.log1p(total_cases) / math.log1p(max_cases_in_dataset)


def _gap_score(n_existing_tips: int, target_tips: int = 5) -> float:
    """1.0 when we know nothing, 0.0 once we have `target_tips` confirmed tips."""
    if n_existing_tips <= 0:
        return 1.0
    if n_existing_tips >= target_tips:
        return 0.0
    return 1.0 - (n_existing_tips / target_tips)


def _staleness_score(
    last_note_at: datetime | None,
    *,
    full_freshness_days: int = 30,
    full_staleness_days: int = 180,
) -> float:
    """0.0 for very recent notes, ramping up to 1.0 by ~6 months."""
    if last_note_at is None:
        return 1.0
    delta = datetime.now(UTC) - last_note_at
    days = delta.total_seconds() / 86400.0
    if days <= full_freshness_days:
        return 0.0
    if days >= full_staleness_days:
        return 1.0
    return (days - full_freshness_days) / (full_staleness_days - full_freshness_days)


def _familiarity_score(driver_deliveries: int, max_deliveries_per_pair: int) -> float:
    """Log-scale how often a driver has delivered to this client."""
    if max_deliveries_per_pair <= 0 or driver_deliveries <= 0:
        return 0.0
    return math.log1p(driver_deliveries) / math.log1p(max_deliveries_per_pair)


def _recency_score(last_delivery: datetime | None) -> float:
    """1.0 if delivered in the last month, decays to 0.0 by 6 months."""
    if last_delivery is None:
        return 0.0
    days = (datetime.now(UTC) - last_delivery).total_seconds() / 86400.0
    if days <= 30:
        return 1.0
    if days >= 180:
        return 0.0
    return 1.0 - ((days - 30) / 150.0)


def _complexity_bonus(pct_returnable: float, has_barrels: bool) -> float:
    """Returnable-heavy clients score a small bump; barrels add more."""
    base = min(1.0, max(0.0, pct_returnable))
    return min(1.0, 0.7 * base + 0.3 * (1.0 if has_barrels else 0.0))


# ---------- queue builder ----------


def _ensure_utc(ts: object) -> datetime | None:
    if ts is None:
        return None
    if isinstance(ts, pd.Timestamp):
        py: datetime = ts.to_pydatetime()
        return py if py.tzinfo else py.replace(tzinfo=UTC)
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    return None


def _has_barrels(top_skus: object) -> bool:
    if not isinstance(top_skus, list):
        return False
    return any(str(s).startswith(("BRL", "ED30", "ED20", "TU20", "TU30", "VO20")) for s in top_skus)


def _build_reason(
    *,
    n_existing_tips: int,
    deliveries: int,
    pct_returnable: float,
    is_chain: bool,
    has_barrels: bool,
) -> str:
    """Short, human-readable reason printed next to each queue entry."""
    bits: list[str] = []
    if n_existing_tips == 0:
        bits.append("no tips yet")
    elif n_existing_tips < 3:
        bits.append(f"only {n_existing_tips} tip(s)")
    if deliveries >= 10:
        bits.append("driver knows the client well")
    elif deliveries >= 3:
        bits.append("driver covered it a few times")
    if has_barrels:
        bits.append("delivers retornable barrels")
    if pct_returnable >= 0.6:
        bits.append("retornable-heavy")
    if is_chain:
        bits.append("chain account")
    return ", ".join(bits) or "baseline candidate"


def build_priority_queue(
    customers: pd.DataFrame,
    affinity: pd.DataFrame,
    notes_summary: pd.DataFrame | None = None,
    *,
    top_n: int = 50,
    weights: ScoringWeights | None = None,
    min_driver_deliveries: int = 2,
) -> pd.DataFrame:
    """Produce a ranked queue of (client, driver) pairs to send to the capture flow.

    Parameters
    ----------
    customers
        Output of `mining.customers.build_customer_profiles`.
    affinity
        Output of `mining.affinity.build_driver_customer_affinity`.
    notes_summary
        Optional frame with one row per `client_id` and the columns
        ``n_existing_tips`` (int) and ``last_note_at`` (datetime). When
        absent we treat every client as having zero tips (cold start).
    top_n
        How many of the highest-scoring pairs to return.
    weights
        Override the default scoring weights.
    min_driver_deliveries
        Filter out (client, driver) pairs where the driver has covered the
        client too few times to be a reliable narrator.
    """

    if customers.empty or affinity.empty:
        logger.warning("empty inputs to priority queue; returning empty frame")
        return pd.DataFrame(columns=list(QUEUE_COLUMNS))

    weights = weights or ScoringWeights()

    aff = affinity[affinity["n_deliveries"] >= min_driver_deliveries].copy()
    if aff.empty:
        logger.warning(
            "all (driver, client) pairs filtered out by min_driver_deliveries=%d",
            min_driver_deliveries,
        )
        return pd.DataFrame(columns=list(QUEUE_COLUMNS))

    # Normalisation anchors for the log-scale factors.
    max_cases = max(1.0, float(customers["total_cases_equiv"].max()))
    max_pair_deliveries = int(max(1, aff["n_deliveries"].max()))

    notes_lookup: dict[str, tuple[int, datetime | None]] = {}
    if notes_summary is not None and not notes_summary.empty:
        for row in notes_summary.itertuples(index=False):
            cid = str(row.client_id)
            n = int(getattr(row, "n_existing_tips", 0) or 0)
            last_at = _ensure_utc(getattr(row, "last_note_at", None))
            notes_lookup[cid] = (n, last_at)

    # Index customer profiles for fast row access.
    cust_by_id: dict[str, pd.Series] = {
        str(row.client_id): row for row in customers.itertuples(index=False)
    }

    rows: list[dict[str, object]] = []
    for pair in aff.itertuples(index=False):
        client_id = str(pair.client_id)
        driver_id = str(pair.driver_id)
        cust = cust_by_id.get(client_id)
        if cust is None:
            continue

        pct_ret = float(getattr(cust, "pct_returnable_lines", 0.0) or 0.0)
        has_barrels = _has_barrels(getattr(cust, "top_skus", None))
        is_chain = str(getattr(cust, "client_kind", "")) == "chain"
        last_delivery = _ensure_utc(getattr(pair, "last_delivery_date", None))

        n_existing_tips, last_note_at = notes_lookup.get(client_id, (0, None))

        s_volume = _volume_score(float(getattr(cust, "total_cases_equiv", 0.0)), max_cases)
        s_gap = _gap_score(n_existing_tips)
        s_stale = _staleness_score(last_note_at)
        s_familiar = _familiarity_score(int(pair.n_deliveries), max_pair_deliveries)
        s_recent = _recency_score(last_delivery)
        s_complex = _complexity_bonus(pct_ret, has_barrels)

        score = (
            weights.volume * s_volume
            + weights.gap * s_gap
            + weights.staleness * s_stale
            + weights.familiarity * s_familiar
            + weights.recency * s_recent
            + weights.complexity * s_complex
        )

        rows.append(
            {
                "client_id": client_id,
                "client_name": str(getattr(cust, "client_name", client_id))[:80],
                "driver_id": driver_id,
                "score": round(score, 4),
                "score_volume": round(s_volume, 4),
                "score_gap": round(s_gap, 4),
                "score_staleness": round(s_stale, 4),
                "score_familiarity": round(s_familiar, 4),
                "score_recency": round(s_recent, 4),
                "score_complexity": round(s_complex, 4),
                "reason": _build_reason(
                    n_existing_tips=n_existing_tips,
                    deliveries=int(pair.n_deliveries),
                    pct_returnable=pct_ret,
                    is_chain=is_chain,
                    has_barrels=has_barrels,
                ),
                "n_existing_tips": n_existing_tips,
                "n_deliveries_driver_to_client": int(pair.n_deliveries),
                "client_total_cases": float(getattr(cust, "total_cases_equiv", 0.0)),
                "client_pct_returnable": round(pct_ret, 4),
                "client_last_delivery": last_delivery,
            }
        )

    out = pd.DataFrame(rows, columns=list(QUEUE_COLUMNS)).sort_values(
        "score", ascending=False, ignore_index=True
    )
    if top_n > 0:
        out = out.head(top_n).reset_index(drop=True)
    logger.info(
        "built priority queue",
        extra={
            "input_pairs": len(aff),
            "output_rows": len(out),
            "weights_total": weights.total(),
        },
    )
    return out


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the parquet files written by `cli profiles`.

    Raises ``DataNotFoundError`` if either file is missing — the caller is
    expected to run the profiles command first.
    """
    settings = get_settings()
    cust_path: Path = settings.profiles_dir / "customers.parquet"
    aff_path: Path = settings.profiles_dir / "driver_customer_affinity.parquet"
    if not cust_path.exists():
        raise DataNotFoundError(f"missing customers profile at {cust_path}")
    if not aff_path.exists():
        raise DataNotFoundError(f"missing driver-customer affinity at {aff_path}")
    return pd.read_parquet(cust_path), pd.read_parquet(aff_path)
