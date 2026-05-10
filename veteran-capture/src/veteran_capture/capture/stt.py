"""Speech-to-text wrapper around the OpenAI Whisper cloud API.

Handles the audio -> transcript step. Multilingual model, robust to ambient
noise, comfortable with the Catalan/Spanish mix the drivers will use.

The local-Whisper alternative (`openai-whisper` package) is intentionally not
imported here: the cloud API is more reliable on a hackathon laptop, the cost
for our volume is negligible (~ $0.03 for the whole demo), and the failure mode
is clearer (HTTP error vs. torch install pain).
"""

from __future__ import annotations

from pathlib import Path

from openai import OpenAI

from veteran_capture.config import get_settings
from veteran_capture.exceptions import ConfigurationError, TranscriptionError
from veteran_capture.logging_setup import get_logger

logger = get_logger(__name__)

# Whisper-1 accepts: mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg.
SUPPORTED_AUDIO_SUFFIXES: frozenset[str] = frozenset(
    {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg"}
)


def _client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key.startswith("sk-"):
        raise ConfigurationError("OPENAI_API_KEY is missing or malformed in .env")
    return OpenAI(api_key=settings.openai_api_key)


def transcribe_audio(
    audio_path: Path,
    *,
    language: str = "es",
) -> str:
    """Send the audio file to Whisper and return the transcript text.

    Parameters
    ----------
    audio_path
        Local file path. Format must be one of `SUPPORTED_AUDIO_SUFFIXES`.
    language
        ISO-639-1 language hint. Defaults to Spanish; pass ``None`` to let
        Whisper auto-detect (slower, sometimes wrong on short clips).

    Raises
    ------
    TranscriptionError
        On unsupported format, empty transcript, or API failure.
    """
    if not audio_path.exists():
        raise TranscriptionError(f"audio file not found: {audio_path}")
    if audio_path.suffix.lower() not in SUPPORTED_AUDIO_SUFFIXES:
        raise TranscriptionError(
            f"unsupported audio suffix {audio_path.suffix!r}; "
            f"supported: {sorted(SUPPORTED_AUDIO_SUFFIXES)}"
        )

    settings = get_settings()
    client = _client()

    logger.info(
        "transcribing audio",
        extra={
            "path": str(audio_path),
            "size_bytes": audio_path.stat().st_size,
            "language": language,
            "model": settings.openai_whisper_model,
        },
    )
    try:
        with audio_path.open("rb") as fh:
            kwargs: dict[str, object] = {
                "model": settings.openai_whisper_model,
                "file": fh,
                "response_format": "text",
            }
            if language:
                kwargs["language"] = language
            response = client.audio.transcriptions.create(**kwargs)  # type: ignore[call-overload]
    except Exception as exc:
        logger.exception("whisper api call failed")
        raise TranscriptionError(f"whisper api error: {exc}") from exc

    transcript = (response if isinstance(response, str) else getattr(response, "text", "")).strip()
    if not transcript:
        raise TranscriptionError("whisper returned an empty transcript")
    logger.info(
        "transcription ok",
        extra={"chars": len(transcript), "preview": transcript[:80]},
    )
    return transcript
