"""Shared Rich console rendering for the interactive agents' tool calls.

The CLI agents (seatunnel config, sql_review, text2sql, data_lineage)
print every tool call and result the same way; only the per-tool border
color and the one-line success summary differ, so both are injected.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.panel import Panel

from ..common.utils import truncate


def display_tool_call(console: Console, name: str, inputs: dict[str, Any],
                      style_map: dict[str, str] | None = None) -> None:
    color = (style_map or {}).get(name, "white")
    args_str = ", ".join(f"{k}={repr(v)[:120]}" for k, v in inputs.items())
    console.print(
        Panel(args_str or "(no arguments)", title=f"Calling: {name}",
              border_style=color)
    )


def display_tool_result(
    console: Console, result: str,
    success_extra: Callable[[dict[str, Any]], str] | None = None,
) -> None:
    """Standard result line: error → red, success → green (+ the agent's
    own ``success_extra(data)`` summary), anything else → dim summary."""
    try:
        data = json.loads(result)
        if data.get("error"):
            console.print(f"  [red]Error:[/red] {str(data['error'])[:200]}")
        elif data.get("success") is True:
            extra = success_extra(data) if success_extra else ""
            console.print(f"  [green]Success[/green]{extra}")
        else:
            console.print(
                f"  [dim]Result received ({len(result)} chars)[/dim]")
    except (json.JSONDecodeError, AttributeError):
        console.print(f"  [dim]Result: {truncate(result, 200)}[/dim]")
