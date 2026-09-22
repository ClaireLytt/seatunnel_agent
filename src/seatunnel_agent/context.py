"""Conversation context management — token estimation and message truncation."""

from __future__ import annotations

from typing import Any

from .config import env_int

# ~100k tokens at 4 chars/token
DEFAULT_MAX_CHARS = env_int("CONTEXT_MAX_CHARS", 400_000)


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


def _is_tool_result_message(message: dict[str, Any]) -> bool:
    """True for messages carrying tool results (Anthropic or OpenAI style)."""
    if message.get("role") == "tool":
        return True
    if message.get("role") == "user":
        content = message.get("content")
        if isinstance(content, list):
            return any(
                isinstance(b, dict) and b.get("type") == "tool_result"
                for b in content
            )
    return False


def truncate_messages(
    messages: list[dict[str, Any]],
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[dict[str, Any]]:
    """Keep recent messages within a character budget.

    Strategy: always keep the most recent messages; drop the oldest
    non-system messages first, inserting a summary marker where the
    cut happened. Tool-use/tool-result pairs are kept or dropped
    together — an orphaned tool_result at the cut boundary would make
    the API reject the request.
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
    start = len(messages) - len(kept_from_end)

    # Drop orphaned tool results at the cut boundary (their paired
    # assistant tool_use message was truncated away).
    while len(kept_from_end) > 1 and _is_tool_result_message(kept_from_end[0]):
        kept_from_end.pop(0)
        start += 1

    # If the only kept message is a tool result, pull earlier messages
    # back in until its owning assistant tool_use is included —
    # correctness over budget.
    if kept_from_end and _is_tool_result_message(kept_from_end[0]):
        while start > 0:
            start -= 1
            kept_from_end.insert(0, messages[start])
            if not _is_tool_result_message(messages[start]):
                break

    if kept_from_end and kept_from_end[0].get("role") != "user":
        result.append({
            "role": "user",
            "content": "[Earlier conversation history was trimmed to fit context window.]",
        })

    result.extend(kept_from_end)
    return result
