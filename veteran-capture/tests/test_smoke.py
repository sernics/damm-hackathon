"""Phase-0 smoke tests: package imports cleanly and settings load with defaults."""

from __future__ import annotations

import os

import pytest

import veteran_capture
from veteran_capture import exceptions, logging_setup, paths
from veteran_capture.config import Settings


def test_package_version_present() -> None:
    assert veteran_capture.__version__ == "0.1.0"


def test_paths_exist() -> None:
    assert paths.PACKAGE_ROOT.exists()
    assert paths.PROJECT_ROOT.exists()
    assert paths.PROJECT_ROOT.name == "veteran-capture"
    assert paths.REPO_ROOT.name == "damm-hackathon"


def test_settings_load_with_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_MODEL",
        "OPENAI_WHISPER_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)
    _ = os  # keep import for type-checkers; explicit usage avoids dead-import lint
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.anthropic_model.startswith("claude")
    assert settings.openai_whisper_model == "whisper-1"
    assert settings.server_port == 8001


def test_logging_setup_idempotent() -> None:
    logging_setup.configure_logging()
    logging_setup.configure_logging()  # second call should not raise
    log = logging_setup.get_logger("veteran_capture.tests")
    assert log.name == "veteran_capture.tests"


def test_exceptions_are_subclasses() -> None:
    assert issubclass(exceptions.ConfigurationError, exceptions.VeteranCaptureError)
    assert issubclass(exceptions.TranscriptionError, exceptions.VeteranCaptureError)
    assert issubclass(exceptions.ExtractionError, exceptions.VeteranCaptureError)
    assert issubclass(exceptions.ModerationRejectedError, exceptions.VeteranCaptureError)
    assert issubclass(exceptions.DataNotFoundError, exceptions.VeteranCaptureError)
