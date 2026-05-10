"""Domain-specific exceptions raised by the veteran-capture pipeline."""

from __future__ import annotations


class VeteranCaptureError(Exception):
    """Base class for all errors raised by this package."""


class ConfigurationError(VeteranCaptureError):
    """Raised when settings are missing or invalid at startup."""


class DataNotFoundError(VeteranCaptureError):
    """Raised when an expected CSV / parquet / markdown file is missing."""


class TranscriptionError(VeteranCaptureError):
    """Raised when STT fails or returns an unusable transcript."""


class ExtractionError(VeteranCaptureError):
    """Raised when the LLM extraction step does not return a valid JSON payload."""


class ModerationRejectedError(VeteranCaptureError):
    """Raised when a tip is filtered out by the moderation pass."""
