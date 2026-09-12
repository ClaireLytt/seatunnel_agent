from __future__ import annotations

import sys

import click
from rich.console import Console

from . import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Show full tracebacks on error")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """SeaTunnel Pipeline Builder Agent — AI-powered SeaTunnel job management."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option("--task", "-t", type=str, default=None, help="Natural language task description")
@click.option(
    "--config", "-c", type=click.Path(), default=None, help="Existing config file to run"
)
@click.pass_context
def run(ctx: click.Context, task: str | None, config: str | None) -> None:
    """Run a SeaTunnel job from a task description or config file."""
    if not task and not config:
        raise click.UsageError("Provide either --task or --config")

    agent = _make_agent()
    try:
        if task:
            result = agent.run(task)
        else:
            result = agent.run_with_config(config)
        console.print(f"\n[bold]Final result:[/bold]\n{result}")
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        _handle_error(e, ctx.obj.get("verbose", False))


@cli.command()
@click.option(
    "--config", "-c", type=click.Path(exists=True), required=True,
    help="Config file to validate",
)
@click.pass_context
def validate(ctx: click.Context, config: str) -> None:
    """Validate a SeaTunnel config file without running it."""
    agent = _make_agent()
    try:
        result = agent.validate_only(config)
        console.print(f"\n[bold]Validation result:[/bold]\n{result}")
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        _handle_error(e, ctx.obj.get("verbose", False))


@cli.command()
@click.option(
    "--log", "-l", type=click.Path(exists=True), required=True,
    help="Log file to diagnose",
)
@click.pass_context
def diagnose(ctx: click.Context, log: str) -> None:
    """Diagnose errors from a SeaTunnel log file."""
    agent = _make_agent()
    try:
        result = agent.diagnose_log(log)
        console.print(f"\n[bold]Diagnosis:[/bold]\n{result}")
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        _handle_error(e, ctx.obj.get("verbose", False))


@cli.command()
@click.option("--port", "-p", type=int, default=7860, help="Port for the web UI")
@click.option("--share", is_flag=True, help="Create a public Gradio link")
def ui(port: int, share: bool) -> None:
    """Launch the Gradio web UI for interactive agent use."""
    try:
        from .ui import create_ui, launch_app
    except ImportError:
        console.print(
            "[red]Gradio is not installed.[/red]\n"
            'Install it with: pip install "seatunnel-agent[ui]"'
        )
        sys.exit(1)

    app = create_ui()
    console.print(f"[green]Starting web UI on http://127.0.0.1:{port}[/green]")
    launch_app(app, port=port, share=share)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_agent():
    from .config import load_settings
    from .agent import SeaTunnelAgent

    settings = load_settings()
    return SeaTunnelAgent(settings)


def _handle_error(e: Exception, verbose: bool) -> None:
    try:
        import anthropic
        if isinstance(e, anthropic.AuthenticationError):
            console.print("[red]Authentication failed.[/red] Check your API_KEY in .env")
            if verbose:
                console.print_exception()
            sys.exit(1)
        elif isinstance(e, anthropic.RateLimitError):
            console.print("[red]Rate limited.[/red] Wait a moment and try again.")
            if verbose:
                console.print_exception()
            sys.exit(1)
        elif isinstance(e, anthropic.APIError):
            console.print(f"[red]Anthropic API error:[/red] {e}")
            if verbose:
                console.print_exception()
            sys.exit(1)
    except ImportError:
        pass

    try:
        import openai
        if isinstance(e, openai.AuthenticationError):
            console.print("[red]Authentication failed.[/red] Check your API_KEY in .env")
            if verbose:
                console.print_exception()
            sys.exit(1)
        elif isinstance(e, openai.RateLimitError):
            console.print("[red]Rate limited.[/red] Wait a moment and try again.")
            if verbose:
                console.print_exception()
            sys.exit(1)
        elif isinstance(e, openai.APIError):
            console.print(f"[red]API error:[/red] {e}")
            if verbose:
                console.print_exception()
            sys.exit(1)
    except ImportError:
        pass

    if isinstance(e, RuntimeError):
        console.print(f"[red]Configuration error:[/red] {e}")
    else:
        console.print(f"[red]Unexpected error:[/red] {e}")
    if verbose:
        console.print_exception()
    sys.exit(1)
