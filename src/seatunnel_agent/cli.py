from __future__ import annotations


import click

from . import __version__
from .cli_common import (  # noqa: F401 — re-exported for cli_cmds back-compat
    _ensure_utf8_stdio,
    _handle_error,
    _write_output,
    console,
)


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Show full tracebacks on error")
@click.option("--model", "-m", default=None, help="Override MODEL_NAME from .env")
@click.option("--provider", default=None, help="Override LLM_PROVIDER from .env")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, model: str | None, provider: str | None) -> None:
    """SeaTunnel Pipeline Builder Agent — AI-powered SeaTunnel job management."""
    _ensure_utf8_stdio()
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["model"] = model
    ctx.obj["provider"] = provider


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


from .cli_cmds import register as _register_commands

_register_commands(cli)


if __name__ == "__main__":
    cli()
