"""Shared adapter from ToolLoopAgent's event stream to the chat agents'
legacy event protocol (thinking / text / tool_call / tool_result, plus
text_delta / usage passthrough).

The four migrated chat agents (sql_review, data_lineage, text2sql,
seatunnel) each carried an identical copy of this mapping; only the Rich
display and the optional per-step hook differ, so both are injected.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

EventCallback = Callable[[str, dict[str, Any]], None]


def legacy_event_adapter(
    emit: EventCallback,
    *,
    display_turn: Callable[[str, str], None],
    display_tool_call: Callable[[str, dict[str, Any]], None],
    display_tool_result: Callable[[str, str], None],
    step_extra: Callable[[dict[str, Any]], None] | None = None,
) -> EventCallback:
    """Build a ToolLoopAgent ``on_event`` that re-emits the legacy protocol.

    ``display_*`` drive the Rich CLI rendering; ``step_extra`` is the hook
    for agent-specific post-processing of an executed tool step (e.g.
    text2sql's sql_retry / cache_hit derivation).
    """
    def adapter(event_type: str, data: dict[str, Any]) -> None:
        if event_type == "turn":
            display_turn(data["thinking"], data["text"])
            if data["thinking"]:
                emit("thinking", {"text": data["thinking"]})
            if data["text"]:
                emit("text", {"text": data["text"]})
        elif event_type == "tool_call":
            display_tool_call(data["name"], data["input"])
            emit("tool_call", data)
        elif event_type == "step":
            display_tool_result(data["tool"], data["output"])
            emit("tool_result", {"name": data["tool"],
                                 "result": data["output"]})
            if step_extra is not None:
                step_extra(data)
        elif event_type in ("text_delta", "usage"):
            emit(event_type, data)

    return adapter


def display_turn_panels(console: Any, thinking: str, text: str) -> None:
    """The default Rich rendering of one model turn (thinking panel +
    plain reply), shared by the chat agents."""
    from rich.panel import Panel

    from ..common.utils import truncate

    if thinking:
        console.print(Panel(truncate(thinking, 500), title="Thinking",
                            border_style="dim", style="italic dim"))
    if text:
        console.print("\n" + text)
