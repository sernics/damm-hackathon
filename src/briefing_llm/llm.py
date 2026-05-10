from __future__ import annotations

from typing import Any

import anthropic

from . import config
from .loader import build_user_message, load_system_prompt, load_tips


def generate_briefing(
    order: dict[str, Any],
    *,
    language: str = "es",
) -> str:
    client_name = order.get("client_name", "")
    tips_markdown = load_tips(client_name)
    system_prompt = load_system_prompt()

    if language == "ca":
        system_prompt += (
            "\n\nThe driver has requested the briefing in Catalan. "
            "Produce the full briefing in Catalan (Catalan from Catalonia)."
        )

    user_message = build_user_message(order, tips_markdown)

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text
