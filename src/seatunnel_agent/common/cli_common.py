# -*- coding: utf-8 -*-
"""Shared console + CLI helpers used by cli.py and every cli_cmds module.

Lives outside both so cli_cmds submodules never import cli.py (which would
be a circular import: cli.py imports cli_cmds at the bottom to register
the commands).
"""

from __future__ import annotations

import sys

from rich.console import Console

console = Console()


def _ensure_utf8_stdio() -> None:
    """Windows consoles/pipes default to GBK; reports carry Chinese text and
    emoji level markers, so a non-UTF-8 stream would raise UnicodeEncodeError
    mid-report (before --output writes and --fail-on gates)."""
    import io
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        enc = getattr(stream, "encoding", None)
        if not enc or enc.lower().replace("-", "") == "utf8":
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, io.UnsupportedOperation):
            buffer = getattr(stream, "buffer", None)
            if buffer is not None:
                setattr(sys, name, io.TextIOWrapper(
                    buffer, encoding="utf-8", errors="replace"))


def _write_output(path: str, content: str) -> None:
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")
    console.print(f"[dim]Result saved to {path}[/dim]")


def _handle_error(e: Exception, verbose: bool) -> None:
    handled = False

    try:
        import anthropic
        if isinstance(e, anthropic.AuthenticationError):
            console.print("[red]Authentication failed.[/red] Check your API_KEY in .env")
            handled = True
        elif isinstance(e, anthropic.RateLimitError):
            console.print("[red]Rate limited.[/red] Wait a moment and try again.")
            handled = True
        elif isinstance(e, anthropic.APIError):
            console.print(f"[red]Anthropic API error:[/red] {e}")
            handled = True
    except ImportError:
        pass

    if not handled:
        try:
            import openai
            if isinstance(e, openai.AuthenticationError):
                console.print("[red]Authentication failed.[/red] Check your API_KEY in .env")
                handled = True
            elif isinstance(e, openai.RateLimitError):
                console.print("[red]Rate limited.[/red] Wait a moment and try again.")
                handled = True
            elif isinstance(e, openai.APIError):
                console.print(f"[red]API error:[/red] {e}")
                handled = True
        except ImportError:
            pass

    if not handled:
        if isinstance(e, RuntimeError):
            console.print(f"[red]Configuration error:[/red] {e}")
        else:
            console.print(f"[red]Unexpected error:[/red] {e}")

    if verbose:
        console.print_exception()
    sys.exit(1)
