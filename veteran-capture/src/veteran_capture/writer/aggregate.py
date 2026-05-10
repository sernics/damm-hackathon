"""Aggregate raw capture JSONs into per-client structures ready for rendering.

Two transformations live here:

1. **Per-topic grouping.** All accepted tips for one client across all captures
   are bucketed by `topic`. The render template iterates these buckets to
   produce the headed sections in the markdown.

2. **Consensus detection.** When two or more distinct drivers contribute tips
   to the same topic for the same client, that topic is flagged as
   `consensus`. The briefing LLM can then trust those tips with high weight.

The aggregator is deterministic and dependency-free: pure Python, no I/O.
The orchestration (loading capture JSONs from disk, writing markdown) lives
in `markdown.py`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from veteran_capture.capture.schemas import CaptureResult, Tip, TopicLiteral

# Order in which topics appear in the rendered markdown. Topics not in this
# list still get a section at the end, in alphabetical order.
TOPIC_ORDER: tuple[TopicLiteral, ...] = (
    "parking",
    "access",
    "contact_person",
    "hours",
    "barrels",
    "empties",
    "warnings",
    "other",
)

# Human-readable section titles, in Spanish to match the briefing audience.
TOPIC_TITLES: dict[TopicLiteral, str] = {
    "parking": "Parking",
    "access": "Acceso al cliente",
    "contact_person": "Contacto / persona de referencia",
    "hours": "Horario real",
    "barrels": "Barriles y carga pesada",
    "empties": "Cascos y retornables",
    "warnings": "Avisos",
    "other": "Otros tips",
}


@dataclass(frozen=True, slots=True)
class TipEntry:
    """A single tip enriched with provenance for the markdown."""

    topic: TopicLiteral
    text: str
    confidence: str
    driver_id: str
    driver_name: str
    captured_at: datetime


@dataclass(slots=True)
class ClientNotesBundle:
    """Everything the renderer needs about one client's tips."""

    client_id: str
    by_topic: dict[TopicLiteral, list[TipEntry]] = field(default_factory=dict)
    consensus_topics: set[TopicLiteral] = field(default_factory=set)
    total_tips: int = 0
    total_drivers: int = 0
    last_updated: datetime | None = None

    def has_topic(self, topic: TopicLiteral) -> bool:
        return bool(self.by_topic.get(topic))

    def topic_in_order(self) -> list[TopicLiteral]:
        seen: set[TopicLiteral] = set()
        out: list[TopicLiteral] = []
        for topic in TOPIC_ORDER:
            if topic in self.by_topic:
                out.append(topic)
                seen.add(topic)
        for topic in sorted(self.by_topic.keys() - seen):
            out.append(topic)
        return out


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _accepted_only(result: CaptureResult) -> list[Tip]:
    """Return moderation-accepted tips, falling back to capture.tips if the
    moderation step was skipped (e.g. zero tips never hit the API)."""
    if result.moderation.accepted:
        return list(result.moderation.accepted)
    if not result.moderation.rejected and result.capture.tips:
        return list(result.capture.tips)
    return []


def aggregate_captures(
    captures: list[CaptureResult],
    *,
    driver_names: dict[str, str] | None = None,
) -> dict[str, ClientNotesBundle]:
    """Group captures by client and bucket their accepted tips by topic.

    Multiple captures for the same client are merged. Tips are sorted within
    each topic by capture timestamp (newest first). Consensus is detected when
    a topic has tips from ``>=2`` distinct drivers.
    """
    driver_names = driver_names or {}
    bundles: dict[str, ClientNotesBundle] = {}

    # Phase 1: collect entries per client per topic.
    raw: dict[str, dict[TopicLiteral, list[TipEntry]]] = defaultdict(lambda: defaultdict(list))
    seen_drivers: dict[str, set[str]] = defaultdict(set)
    last_seen: dict[str, datetime] = {}

    for result in captures:
        client_id = result.capture.client_id
        captured_at = result.capture.captured_at
        driver_id = result.capture.driver_id
        driver_name = driver_names.get(driver_id, driver_id)
        seen_drivers[client_id].add(driver_id)
        if client_id not in last_seen or captured_at > last_seen[client_id]:
            last_seen[client_id] = captured_at

        for tip in _accepted_only(result):
            entry = TipEntry(
                topic=tip.topic,
                text=tip.text,
                confidence=tip.confidence,
                driver_id=driver_id,
                driver_name=driver_name,
                captured_at=captured_at,
            )
            raw[client_id][tip.topic].append(entry)

    # Phase 2: build the public bundles, sort tips, compute consensus.
    for client_id, topics in raw.items():
        sorted_topics: dict[TopicLiteral, list[TipEntry]] = {}
        consensus_topics: set[TopicLiteral] = set()
        total_tips = 0
        for topic, entries in topics.items():
            entries_sorted = sorted(entries, key=lambda e: e.captured_at, reverse=True)
            sorted_topics[topic] = entries_sorted
            total_tips += len(entries_sorted)
            distinct_drivers_in_topic = {e.driver_id for e in entries_sorted}
            if len(distinct_drivers_in_topic) >= 2:
                consensus_topics.add(topic)
        bundles[client_id] = ClientNotesBundle(
            client_id=client_id,
            by_topic=sorted_topics,
            consensus_topics=consensus_topics,
            total_tips=total_tips,
            total_drivers=len(seen_drivers[client_id]),
            last_updated=last_seen[client_id],
        )
    return bundles


def summarise_for_selection(
    bundles: dict[str, ClientNotesBundle],
) -> list[dict[str, object]]:
    """Compact summary used by the selection algorithm's ``notes_summary``.

    One row per client with the columns ``client_id``, ``n_existing_tips``,
    ``last_note_at``. Clients with zero tips are omitted (the selection
    algorithm assumes zero by default).
    """
    out: list[dict[str, object]] = []
    for bundle in bundles.values():
        if bundle.total_tips == 0:
            continue
        out.append(
            {
                "client_id": bundle.client_id,
                "n_existing_tips": bundle.total_tips,
                "last_note_at": bundle.last_updated,
            }
        )
    return out
