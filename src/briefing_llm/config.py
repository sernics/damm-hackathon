from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

MODEL = os.environ.get("BRIEFING_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.environ.get("BRIEFING_MAX_TOKENS", "1024"))

DATASET_DIR = PROJECT_ROOT / "dataset"
ORDERS_CSV = DATASET_DIR / "daily_client_orders.csv"
MANIFEST_PATH = DATASET_DIR / "veteran_notes" / "manifest.json"

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.txt"
USER_TEMPLATE_PATH = PROMPTS_DIR / "user.txt"
