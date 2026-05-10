"""Public data contracts for the capture pipeline.

These shapes are what the extraction LLM emits, what the moderation pass
filters, and what the markdown writer (Phase 4) consumes. Stable: changing
fields here means changing the prompt, the writer, and the briefing-LLM RAG
contract on the other side of the wall.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Allowed topic codes - must match the prompt and the markdown sections.
TopicLiteral = Literal[
    "parking",
    "access",
    "contact_person",
    "barrels",
    "empties",
    "hours",
    "warnings",
    "other",
]

ConfidenceLiteral = Literal["high", "medium", "low"]


class Tip(BaseModel):
    """One actionable piece of veteran knowledge about a single client."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    topic: TopicLiteral
    text: str = Field(..., min_length=3, max_length=500)
    confidence: ConfidenceLiteral = "medium"


class ExtractedCapture(BaseModel):
    """The structured output of one capture cycle (one audio -> tips)."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    client_id: str
    driver_id: str
    captured_at: datetime
    tips: list[Tip] = Field(default_factory=list)
    raw_transcript: str = ""
    audio_seconds: float | None = None


class ModerationVerdict(BaseModel):
    """Output of the moderation pass that filters inappropriate content."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    accepted: list[Tip] = Field(default_factory=list)
    rejected: list[Tip] = Field(default_factory=list)
    notes: str | None = None


class CaptureResult(BaseModel):
    """Top-level response returned by the web layer to the driver UI."""

    model_config = ConfigDict(extra="ignore")

    capture: ExtractedCapture
    moderation: ModerationVerdict
