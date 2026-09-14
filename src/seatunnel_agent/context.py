"""Conversation context management — token estimation and message truncation."""

from __future__ import annotations

from typing import Any

DEFAULT_MAX_CHARS = 400_000  # ~100k tokens at 4 chars/token


def _estimate_chars(message: dict[str, Any]) -> int:
    """Rough character count for a single message."""
    content = message.get("content", "")
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            if isinstance(block, dict):
                total += len(str(block.get("text", "")))
                total += len(str(block.get("content", "")))
                total += len(str(block.get("input", "")))
            elif isinstance(block, str):
                total += len(block)
        return total
    return len(str(content))


def truncate_messages(
    messages: list[dict[str, Any]],
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[dict[str, Any]]:
    """Keep recent messages within a character budget.

    Strategy: always keep the most recent messages; drop the oldest
    non-system messages first, inserting a summary marker where the
    cut happened.
    """
    if not messages:
        return messages

    total = sum(_estimate_chars(m) for m in messages)
    if total <= max_chars:
        return messages

    result: list[dict[str, Any]] = []
    kept_from_end: list[dict[str, Any]] = []
    running = 0

    for m in reversed(messages):
        cost = _estimate_chars(m)
        if running + cost > max_chars and kept_from_end:
            break
        kept_from_end.append(m)
        running += cost

    kept_from_end.reverse()

    if kept_from_end and kept_from_end[0].get("role") != "user":
        result.append({
            "role": "user",
            "content": "[Earlier conversation history was trimmed to fit context window.]",
        })

    result.extend(kept_from_end)
    return result
