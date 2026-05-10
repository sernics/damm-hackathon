"""Targeted tests for the selection algorithm.

Only the cases where we'd actually catch a regression: ranking direction,
notes-summary effect, and the empty-input edge case. No exhaustive
parametrisation — the value here is sanity, not coverage.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from veteran_capture.selection import (
    ScoringWeights,
    build_priority_queue,
)


def _customers() -> pd.DataFrame:
    """Two customers: a heavy returnable-barrel client and a light one-shot client."""
    return pd.DataFrame(
        [
            {
                "client_id": "9100000001",
                "client_name": "BAR EL TUPI",
                "client_kind": "individual",
                "total_cases_equiv": 1500.0,
                "pct_returnable_lines": 0.7,
                "top_skus": ["ED13", "BRL30V", "VE12SP"],
            },
            {
                "client_id": "9100000002",
                "client_name": "QUIOSCO PEQUE",
                "client_kind": "individual",
                "total_cases_equiv": 30.0,
                "pct_returnable_lines": 0.05,
                "top_skus": ["VE12SP"],
            },
        ]
    )


def _affinity() -> pd.DataFrame:
    """Driver A knows the heavy client well; driver B has covered the small one once."""
    return pd.DataFrame(
        [
            {
                "driver_id": "850001",
                "client_id": "9100000001",
                "n_deliveries": 30,
                "n_lines": 200,
                "first_delivery_date": pd.Timestamp("2026-01-01", tz="UTC"),
                "last_delivery_date": pd.Timestamp("2026-04-25", tz="UTC"),
                "total_cases_equiv": 1200.0,
            },
            {
                "driver_id": "850002",
                "client_id": "9100000001",
                "n_deliveries": 3,
                "n_lines": 12,
                "first_delivery_date": pd.Timestamp("2026-02-10", tz="UTC"),
                "last_delivery_date": pd.Timestamp("2026-04-20", tz="UTC"),
                "total_cases_equiv": 80.0,
            },
            {
                "driver_id": "850002",
                "client_id": "9100000002",
                "n_deliveries": 2,
                "n_lines": 4,
                "first_delivery_date": pd.Timestamp("2026-03-01", tz="UTC"),
                "last_delivery_date": pd.Timestamp("2026-04-30", tz="UTC"),
                "total_cases_equiv": 30.0,
            },
        ]
    )


def test_heavy_client_ranks_above_small_client() -> None:
    queue = build_priority_queue(_customers(), _affinity())
    assert not queue.empty
    # Best (driver, client) row should be the veteran covering the heavy client.
    top = queue.iloc[0]
    assert top["client_id"] == "9100000001"
    assert top["driver_id"] == "850001"
    assert "driver knows the client well" in top["reason"]
    assert "retornable" in top["reason"] or "barrels" in top["reason"]


def test_existing_notes_lower_priority_via_gap_score() -> None:
    customers = _customers()
    affinity = _affinity()
    notes_full = pd.DataFrame(
        [
            {
                "client_id": "9100000001",
                "n_existing_tips": 6,
                "last_note_at": datetime.now(UTC) - timedelta(days=5),
            }
        ]
    )
    queue_with_notes = build_priority_queue(customers, affinity, notes_summary=notes_full)
    queue_cold = build_priority_queue(customers, affinity)

    score_with_notes = float(
        queue_with_notes[queue_with_notes["client_id"] == "9100000001"]["score"].iloc[0]
    )
    score_cold = float(
        queue_cold[queue_cold["client_id"] == "9100000001"]["score"].iloc[0]
    )
    assert score_with_notes < score_cold


def test_min_driver_deliveries_filters_inexperienced_pairs() -> None:
    queue = build_priority_queue(_customers(), _affinity(), min_driver_deliveries=10)
    assert (queue["n_deliveries_driver_to_client"] >= 10).all()
    assert all(queue["driver_id"] == "850001")


def test_weights_total_close_to_one() -> None:
    # Sanity check on the defaults; not strict, just keeps weights honest.
    assert abs(ScoringWeights().total() - 1.0) < 1e-9


def test_empty_inputs_return_empty_queue() -> None:
    empty = pd.DataFrame()
    assert build_priority_queue(empty, empty).empty
