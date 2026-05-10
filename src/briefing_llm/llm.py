from __future__ import annotations

from typing import Any

import anthropic

from . import config
from .loader import build_user_message, collect_all_tips, load_system_prompt


def generate_briefing(
    route: dict[str, Any],
    *,
    language: str = "es",
) -> str:
    stops = route.get("stops", [])
    all_tips = collect_all_tips(stops)
    system_prompt = load_system_prompt()

    if language == "ca":
        system_prompt += (
            "\n\nThe driver has requested the briefing in Catalan. "
            "Produce the full briefing in Catalan (Catalan from Catalonia)."
        )

    user_message = build_user_message(route, all_tips)

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text
