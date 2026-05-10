"""Canonical filesystem paths for the veteran-capture package.

Resolved relative to the package root unless overridden by environment variables
through `Settings`. Centralised here so every module imports the same locations.
"""

from __future__ import annotations

from pathlib import Path

# Package-internal anchors
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]  # veteran-capture/
REPO_ROOT = PROJECT_ROOT.parent  # damm-hackathon/

# Default locations (override via Settings)
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_RAW_CSV_DIR = REPO_ROOT / "data" / "csv" / "Hackaton"
DEFAULT_GEOCODED_CSV = REPO_ROOT / "data" / "custom" / "geo" / "geocoded_direcciones.csv"
DEFAULT_VETERAN_NOTES_DIR = REPO_ROOT / "dataset" / "veteran_notes"
DEFAULT_PROFILES_DIR = DEFAULT_DATA_DIR / "profiles"
DEFAULT_QUEUES_DIR = DEFAULT_DATA_DIR / "queues"
DEFAULT_AUDIO_DIR = DEFAULT_DATA_DIR / "audio"
