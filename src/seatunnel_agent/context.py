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

    # 截断点若落在 tool_use/tool_result 对中间，开头的 tool_result
    # 找不到对应的 tool_use，API 会直接报 400 —— 连带丢弃这些消息。
    # openai 兼容格式的工具结果是 role=="tool"，同样要弹出。
    def _leads_with_tool_result(m: dict[str, Any]) -> bool:
        if m.get("role") == "tool":
            return True
        content = m.get("content")
        return isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result"
            for b in content
        )

    while kept_from_end and _leads_with_tool_result(kept_from_end[0]):
        kept_from_end.pop(0)

    if not kept_from_end:
        # 预算连一条完整消息都留不下：至少保留最近一个 user 轮，
        # 绝不能返回空列表（调用方会用返回值覆盖会话历史）
        for i in range(len(messages) - 1, -1, -1):
            m = messages[i]
            if m.get("role") == "user" and not _leads_with_tool_result(m):
                kept_from_end = list(messages[i:])
                break
        if not kept_from_end:
            return messages

    if kept_from_end and kept_from_end[0].get("role") != "user":
        result.append({
            "role": "user",
            "content": "[Earlier conversation history was trimmed to fit context window.]",
        })

    result.extend(kept_from_end)
    return result
