from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

MODEL = os.environ.get("BRIEFING_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.environ.get("BRIEFING_MAX_TOKENS", "1024"))

DATA_DIR = Path(os.environ.get("BRIEFING_DATA_DIR", PROJECT_ROOT / "data" / "briefing-llm-template"))
TIPS_DIR = DATA_DIR / "tips"
PROMPTS_DIR = DATA_DIR / "prompts"

SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.sample.txt"
USER_TEMPLATE_PATH = PROMPTS_DIR / "user.placeholder.txt"
