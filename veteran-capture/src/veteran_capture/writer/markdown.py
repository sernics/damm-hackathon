"""Render the veteran-notes Markdown knowledge base from capture JSONs.

Workflow:

1. Load every JSON in `data/captures/*.json`. Each is a `CaptureResult`.
2. Aggregate them by client (`aggregate.aggregate_captures`).
3. Cross-reference with the customer profile parquet for "quick facts".
4. Render `<client_id>.md` for every client that has at least one tip.
5. Render `_manifest.md` and `manifest.json` listing every active client
   in priority order, with status (filled / empty), suggested next driver,
   and a link to the per-client markdown when it exists.

The output directory is `settings.veteran_notes_dir` (defaults to
`../dataset/veteran_notes/` so Person B's RAG can ingest it).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import ValidationError

import veteran_capture
from veteran_capture.capture.schemas import CaptureResult
from veteran_capture.config import get_settings
from veteran_capture.exceptions import DataNotFoundError
from veteran_capture.logging_setup import get_logger
from veteran_capture.selection import build_priority_queue
from veteran_capture.writer.aggregate import (
    TOPIC_TITLES,
    ClientNotesBundle,
    aggregate_captures,
    summarise_for_selection,
)

logger = get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_ENV = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(default=False, default_for_string=False),
    trim_blocks=False,
    lstrip_blocks=False,
    keep_trailing_newline=True,
)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def load_captures(captures_dir: Path) -> list[CaptureResult]:
    """Read every `.json` in `captures_dir` and parse as `CaptureResult`."""
    if not captures_dir.exists():
        return []
    out: list[CaptureResult] = []
    bad = 0
    for path in sorted(captures_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            out.append(CaptureResult.model_validate(payload))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("skipping malformed capture", extra={"path": str(path), "error": str(exc)})
            bad += 1
    logger.info(
        "loaded captures",
        extra={"path": str(captures_dir), "loaded": len(out), "skipped": bad},
    )
    return out


def load_customers() -> pd.DataFrame:
    settings = get_settings()
    path = settings.profiles_dir / "customers.parquet"
    if not path.exists():
        raise DataNotFoundError(f"customers profile not built: {path}")
    return pd.read_parquet(path)


def load_driver_names() -> dict[str, str]:
    """Map driver_id -> display name from Cabecera_Transporte.csv."""
    settings = get_settings()
    cab_path = settings.raw_csv_dir / "Cabecera_Transporte.csv"
    if not cab_path.exists():
        return {}
    cab = pd.read_csv(cab_path, dtype=str, keep_default_na=False)
    cab.columns = [c.strip() for c in cab.columns]
    if "Repartidor" not in cab.columns or "Unnamed: 5" not in cab.columns:
        return {}
    pairs = (
        cab[["Repartidor", "Unnamed: 5"]]
        .dropna()
        .drop_duplicates()
        .rename(columns={"Repartidor": "id", "Unnamed: 5": "name"})
    )
    return {str(r["id"]).strip(): str(r["name"]).strip() for _, r in pairs.iterrows()}


# ---------------------------------------------------------------------------
# Per-client rendering
# ---------------------------------------------------------------------------


def _safe_list(value: Any) -> list[str]:
    if value is None:
        return []
    try:
        return [str(v) for v in value]
    except TypeError:
        return []


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _frequency_label(days: float | None) -> str:
    if days is None or days <= 0:
        return "—"
    if days <= 4:
        return "varias veces / semana"
    if days <= 9:
        return "semanal aprox."
    if days <= 18:
        return "quincenal aprox."
    if days <= 35:
        return "mensual aprox."
    return f"cada {days:.0f} dias aprox."


def _client_facts(row: pd.Series, capture_count: int) -> dict[str, Any]:
    return {
        "client_id": _safe_str(row.get("client_id")),
        "client_name": _safe_str(row.get("client_name")) or _safe_str(row.get("client_id")),
        "address": ", ".join(
            x
            for x in (
                _safe_str(row.get("calle")),
                _safe_str(row.get("cp")),
                _safe_str(row.get("poblacion")),
            )
            if x
        ),
        "zone": _safe_str(row.get("zone_code")) or None,
        "client_kind": _safe_str(row.get("client_kind")) or None,
        "n_deliveries": int(row.get("n_deliveries") or 0),
        "mean_cases": float(row.get("mean_cases_per_delivery") or 0.0),
        "total_cases": float(row.get("total_cases_equiv") or 0.0),
        "pct_returnable": float(row.get("pct_returnable_lines") or 0.0),
        "frequency_label": _frequency_label(
            float(row.get("delivery_frequency_days") or 0.0) or None
        ),
        "top_skus": _safe_list(row.get("top_skus")),
        "has_schedule": bool(row.get("has_schedule") or False),
        "drivers_seen": _safe_list(row.get("drivers_seen")),
        "n_capture_files": capture_count,
    }


def render_client_markdown(
    bundle: ClientNotesBundle,
    facts: dict[str, Any],
    *,
    generated_at: datetime,
) -> str:
    template = _ENV.get_template("client.md.j2")
    return template.render(
        version=veteran_capture.__version__,
        generated_at=generated_at.strftime("%Y-%m-%d %H:%M UTC"),
        topic_order=bundle.topic_in_order(),
        topic_titles=TOPIC_TITLES,
        by_topic=bundle.by_topic,
        consensus_topics=bundle.consensus_topics,
        total_tips=bundle.total_tips,
        total_drivers=bundle.total_drivers,
        last_updated=bundle.last_updated,
        **facts,
    )


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _ManifestEntry:
    rank: int
    client_id: str
    client_name: str
    status: str  # "filled" | "empty"
    n_tips: int
    n_drivers: int
    topics: list[str]
    consensus_topics: list[str]
    tips: list[dict[str, Any]]  # full content for filled clients, empty list otherwise
    suggested_driver_id: str | None
    suggested_driver_name: str | None
    priority_score: float
    total_cases: float
    n_deliveries: int
    pct_returnable: float
    last_updated: datetime | None
    address: str
    zone: str | None
    notes_path: str | None  # relative path to <client_id>.md, or None if empty


def _load_affinity_for_manifest() -> pd.DataFrame:
    settings = get_settings()
    path = settings.profiles_dir / "driver_customer_affinity.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["client_id", "driver_id", "n_deliveries"])
    return pd.read_parquet(path)


def _suggest_drivers_per_client(
    customers: pd.DataFrame,
    affinity: pd.DataFrame,
    bundles: dict[str, ClientNotesBundle],
) -> dict[str, tuple[str, float]]:
    """Best (driver_id, score) per client according to the priority queue.

    Uses the same scoring as the live priority queue, but computed per
    (client, driver) and then collapsed to one row per client (the
    highest-scoring driver). Clients without an eligible driver (none
    with the minimum delivery count) are absent from the dict; the
    caller falls back to a volume-only proxy score for them.
    """
    suggestions: dict[str, tuple[str, float]] = {}
    if customers.empty or affinity.empty:
        return suggestions

    notes_summary_rows = summarise_for_selection(bundles)
    notes_summary = pd.DataFrame(notes_summary_rows) if notes_summary_rows else None

    queue = build_priority_queue(
        customers,
        affinity,
        notes_summary=notes_summary,
        top_n=0,
        min_driver_deliveries=2,
    )
    if queue.empty:
        return suggestions
    best_per_client = queue.sort_values("score", ascending=False).drop_duplicates(
        "client_id", keep="first"
    )
    for _, row in best_per_client.iterrows():
        cid = str(row["client_id"])
        suggestions[cid] = (str(row["driver_id"]), float(row["score"]))
    return suggestions


def _fallback_score(row: pd.Series, has_notes: bool) -> float:
    """Cheap score for clients that have no eligible driver in the queue.

    Volume-only proxy in [0, 1], lightly penalised when notes already exist.
    Keeps such clients sortable in the manifest without needing a driver.
    """
    cases = float(row.get("total_cases_equiv") or 0.0)
    base = 0.0 if cases <= 0 else min(1.0, math.log1p(cases) / math.log1p(10000.0))
    return base * (0.5 if has_notes else 1.0) * 0.30


def build_manifest_entries(
    customers: pd.DataFrame,
    bundles: dict[str, ClientNotesBundle],
    driver_names: dict[str, str],
) -> list[_ManifestEntry]:
    """Produce one entry per active customer, sorted by priority desc."""
    affinity = _load_affinity_for_manifest()
    suggestions = _suggest_drivers_per_client(customers, affinity, bundles)

    entries: list[_ManifestEntry] = []
    for _, row in customers.iterrows():
        client_id = _safe_str(row.get("client_id"))
        if not client_id:
            continue
        bundle = bundles.get(client_id)
        has_notes = bundle is not None and bundle.total_tips > 0

        match = suggestions.get(client_id)
        if match is None:
            suggested_id = None
            score = _fallback_score(row, has_notes)
        else:
            suggested_id, score = match

        topics_titles: list[str] = []
        consensus_codes: list[str] = []
        tip_dicts: list[dict[str, Any]] = []
        if bundle is not None:
            topics_titles = [TOPIC_TITLES.get(t, t) for t in bundle.topic_in_order()]
            consensus_codes = sorted(bundle.consensus_topics)
            for topic in bundle.topic_in_order():
                for entry_tip in bundle.by_topic.get(topic, []):
                    tip_dicts.append(
                        {
                            "topic": entry_tip.topic,
                            "topic_label": TOPIC_TITLES.get(
                                entry_tip.topic, entry_tip.topic
                            ),
                            "text": entry_tip.text,
                            "confidence": entry_tip.confidence,
                            "driver_id": entry_tip.driver_id,
                            "driver_name": entry_tip.driver_name,
                            "captured_at": entry_tip.captured_at.isoformat(),
                            "consensus": entry_tip.topic in bundle.consensus_topics,
                        }
                    )

        entries.append(
            _ManifestEntry(
                rank=0,  # filled in after sort
                client_id=client_id,
                client_name=_safe_str(row.get("client_name")) or client_id,
                status="filled" if has_notes else "empty",
                n_tips=bundle.total_tips if bundle else 0,
                n_drivers=bundle.total_drivers if bundle else 0,
                topics=topics_titles,
                consensus_topics=consensus_codes,
                tips=tip_dicts,
                suggested_driver_id=suggested_id,
                suggested_driver_name=(
                    driver_names.get(suggested_id, suggested_id)
                    if suggested_id
                    else None
                ),
                priority_score=round(float(score), 4),
                total_cases=float(row.get("total_cases_equiv") or 0.0),
                n_deliveries=int(row.get("n_deliveries") or 0),
                pct_returnable=float(row.get("pct_returnable_lines") or 0.0),
                last_updated=bundle.last_updated if bundle else None,
                address=", ".join(
                    x
                    for x in (
                        _safe_str(row.get("calle")),
                        _safe_str(row.get("cp")),
                        _safe_str(row.get("poblacion")),
                    )
                    if x
                ),
                zone=_safe_str(row.get("zone_code")) or None,
                notes_path=f"{client_id}.md" if has_notes else None,
            )
        )

    entries.sort(key=lambda e: (-e.priority_score, e.client_id))
    for i, entry in enumerate(entries, start=1):
        entry.rank = i
    return entries


def _manifest_to_json(
    entries: list[_ManifestEntry], generated_at: datetime
) -> dict[str, Any]:
    filled = sum(1 for e in entries if e.status == "filled")
    return {
        "version": veteran_capture.__version__,
        "generated_at": generated_at.isoformat(),
        "total_clients": len(entries),
        "filled": filled,
        "empty": len(entries) - filled,
        "entries": [
            {
                "rank": e.rank,
                "client_id": e.client_id,
                "client_name": e.client_name,
                "status": e.status,
                "n_tips": e.n_tips,
                "n_drivers": e.n_drivers,
                "topics": e.topics,
                "consensus_topics": e.consensus_topics,
                "suggested_driver_id": e.suggested_driver_id,
                "suggested_driver_name": e.suggested_driver_name,
                "priority_score": e.priority_score,
                "total_cases": e.total_cases,
                "n_deliveries": e.n_deliveries,
                "pct_returnable": round(e.pct_returnable, 4),
                "last_updated": (
                    e.last_updated.isoformat() if e.last_updated else None
                ),
                "address": e.address,
                "zone": e.zone,
                "notes_path": e.notes_path,
                "tips": e.tips,
            }
            for e in entries
        ],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WriteReport:
    clients_written: int
    captures_loaded: int
    out_dir: Path
    manifest_md_path: Path
    manifest_json_path: Path
    total_clients: int
    filled: int
    empty: int


def _cleanup_legacy_outputs(out_dir: Path) -> None:
    """Remove the deprecated _index.md and _gaps.md files if present."""
    for stale in ("_index.md", "_gaps.md"):
        path = out_dir / stale
        if path.exists():
            path.unlink()
            logger.info("removed legacy output", extra={"path": str(path)})


def write_all_notes(*, manifest_top_recommend: int = 20) -> WriteReport:
    settings = get_settings()
    captures_dir = settings.data_dir / "captures"
    out_dir = settings.veteran_notes_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    captures = load_captures(captures_dir)
    customers = load_customers()
    driver_names = load_driver_names()
    bundles = aggregate_captures(captures, driver_names=driver_names)

    customers_by_id = {str(r["client_id"]): r for _, r in customers.iterrows()}
    capture_counts: dict[str, int] = {}
    for result in captures:
        cid = result.capture.client_id
        capture_counts[cid] = capture_counts.get(cid, 0) + 1

    generated_at = datetime.now(UTC)
    written_clients = 0
    for client_id, bundle in bundles.items():
        row = customers_by_id.get(client_id)
        facts = (
            _client_facts(row, capture_counts.get(client_id, 0))
            if row is not None
            else {
                "client_id": client_id,
                "client_name": client_id,
                "address": "",
                "zone": None,
                "client_kind": None,
                "n_deliveries": 0,
                "mean_cases": 0.0,
                "total_cases": 0.0,
                "pct_returnable": 0.0,
                "frequency_label": "—",
                "top_skus": [],
                "has_schedule": False,
                "drivers_seen": [],
                "n_capture_files": capture_counts.get(client_id, 0),
            }
        )
        markdown = render_client_markdown(bundle, facts, generated_at=generated_at)
        target = out_dir / f"{client_id}.md"
        target.write_text(markdown, encoding="utf-8")
        written_clients += 1

    # Manifest
    entries = build_manifest_entries(customers, bundles, driver_names)
    filled = sum(1 for e in entries if e.status == "filled")
    empty = len(entries) - filled

    manifest_md_path = out_dir / "_manifest.md"
    manifest_template = _ENV.get_template("_manifest.md.j2")
    manifest_md_path.write_text(
        manifest_template.render(
            version=veteran_capture.__version__,
            generated_at=generated_at.strftime("%Y-%m-%d %H:%M UTC"),
            entries=entries,
            total_clients=len(entries),
            filled=filled,
            empty=empty,
            top_recommend=min(manifest_top_recommend, len(entries)),
        ),
        encoding="utf-8",
    )

    manifest_json_path = out_dir / "manifest.json"
    manifest_json_path.write_text(
        json.dumps(
            _manifest_to_json(entries, generated_at), ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )

    _cleanup_legacy_outputs(out_dir)

    report = WriteReport(
        clients_written=written_clients,
        captures_loaded=len(captures),
        out_dir=out_dir,
        manifest_md_path=manifest_md_path,
        manifest_json_path=manifest_json_path,
        total_clients=len(entries),
        filled=filled,
        empty=empty,
    )
    logger.info(
        "wrote veteran notes",
        extra={
            "out_dir": str(out_dir),
            "clients_written": written_clients,
            "captures_loaded": len(captures),
            "manifest_filled": filled,
            "manifest_empty": empty,
        },
    )
    return report
