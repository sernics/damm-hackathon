from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config


def load_order(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def load_order_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    return data


def find_tips_file(client_name: str, tips_dir: Path | None = None) -> Path | None:
    tips_dir = tips_dir or config.TIPS_DIR
    candidate = tips_dir / f"{client_name}.md"
    if candidate.exists():
        return candidate
    for md in tips_dir.glob("*.md"):
        if md.stem == "_TEMPLATE":
            continue
        if md.stem.strip().upper() == client_name.strip().upper():
            return md
    return None


def load_tips(client_name: str, tips_dir: Path | None = None) -> str:
    path = find_tips_file(client_name, tips_dir)
    if path is None:
        return ""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    in_frontmatter = False
    body_lines: list[str] = []
    for line in lines:
        if line.strip() == "---":
            in_frontmatter = not in_frontmatter
            continue
        if not in_frontmatter:
            body_lines.append(line)
    return "\n".join(body_lines).strip()


def load_system_prompt() -> str:
    return config.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_user_message(order: dict[str, Any], tips_markdown: str) -> str:
    template = config.USER_TEMPLATE_PATH.read_text(encoding="utf-8")
    order_json_str = json.dumps(order, ensure_ascii=False, indent=2)
    message = template.replace("{{ order_json }}", order_json_str)
    message = message.replace("{{ veteran_tips_markdown }}", tips_markdown or "(No tips available for this client.)")
    return message
