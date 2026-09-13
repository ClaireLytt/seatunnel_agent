from __future__ import annotations

import os
import sys

import click
from rich.console import Console

from . import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Show full tracebacks on error")
@click.option("--model", "-m", default=None, help="Override MODEL_NAME from .env")
@click.option("--provider", default=None, help="Override LLM_PROVIDER from .env")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, model: str | None, provider: str | None) -> None:
    """SeaTunnel Pipeline Builder Agent — AI-powered SeaTunnel job management."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["model"] = model
    ctx.obj["provider"] = provider


@cli.command()
@click.option("--task", "-t", type=str, default=None, help="Natural language task description")
@click.option(
    "--config", "-c", type=click.Path(), default=None, help="Existing config file to run"
)
@click.option("--output", "-o", type=click.Path(), default=None, help="Save result to file")
@click.pass_context
def run(ctx: click.Context, task: str | None, config: str | None, output: str | None) -> None:
    """Run a SeaTunnel job from a task description or config file."""
    if not task and not config:
        raise click.UsageError("Provide either --task or --config")

    agent = _make_agent(model=ctx.obj.get("model"), provider=ctx.obj.get("provider"))
    _run_command(
        lambda: agent.run(task) if task else agent.run_with_config(config),
        label="Final result",
        output=output,
        verbose=ctx.obj.get("verbose", False),
    )


@cli.command()
@click.option(
    "--config", "-c", type=click.Path(exists=True), required=True,
    help="Config file to validate",
)
@click.option("--output", "-o", type=click.Path(), default=None, help="Save result to file")
@click.pass_context
def validate(ctx: click.Context, config: str, output: str | None) -> None:
    """Validate a SeaTunnel config file without running it."""
    agent = _make_agent(model=ctx.obj.get("model"), provider=ctx.obj.get("provider"))
    _run_command(
        lambda: agent.validate_only(config),
        label="Validation result",
        output=output,
        verbose=ctx.obj.get("verbose", False),
    )


@cli.command()
@click.option(
    "--log", "-l", type=click.Path(exists=True), required=True,
    help="Log file to diagnose",
)
@click.option("--output", "-o", type=click.Path(), default=None, help="Save result to file")
@click.pass_context
def diagnose(ctx: click.Context, log: str, output: str | None) -> None:
    """Diagnose errors from a SeaTunnel log file."""
    agent = _make_agent(model=ctx.obj.get("model"), provider=ctx.obj.get("provider"))
    _run_command(
        lambda: agent.diagnose_log(log),
        label="Diagnosis",
        output=output,
        verbose=ctx.obj.get("verbose", False),
    )


@cli.command()
@click.option("--resume", "-r", default=None, help="Resume session by ID")
@click.option("--list-sessions", is_flag=True, help="List recent sessions and exit")
@click.pass_context
def chat(ctx: click.Context, resume: str | None, list_sessions: bool) -> None:
    """Start an interactive multi-turn chat session with the Agent."""
    from .history import load_session, save_session, new_session_id, now_iso, Session
    from .history import list_sessions as _list_sessions

    if list_sessions:
        sessions = _list_sessions()
        if not sessions:
            console.print("[yellow]No saved sessions found.[/yellow]")
        else:
            console.print("[bold]Recent sessions:[/bold]")
            for s in sessions[:20]:
                console.print(f"  [cyan]{s['id']}[/cyan]  {s['title']}  ({s.get('msg_count', 0)} msgs, {s['updated_at']})")
        return

    agent = _make_agent(model=ctx.obj.get("model"), provider=ctx.obj.get("provider"))

    session: Session | None = None
    if resume:
        session = load_session(resume)
        if session is None:
            console.print(f"[red]Session '{resume}' not found.[/red]")
            sys.exit(1)
        agent.messages = session.agent_messages
        agent.context = session.agent_context
        console.print(f"[green]Resumed session: {session.title} ({session.session_id})[/green]")
    else:
        session = Session(
            session_id=new_session_id(),
            title="Untitled",
            created_at=now_iso(),
            updated_at=now_iso(),
        )

    console.print("[green]SeaTunnel Agent — interactive chat (type 'exit' or 'quit' to stop)[/green]\n")
    try:
        while True:
            try:
                msg = input("You: ").strip()
            except EOFError:
                break
            if not msg:
                continue
            if msg.lower() in ("exit", "quit"):
                break
            try:
                result = agent.chat(msg)
                session.chat_messages.append({"role": "user", "content": msg})
                session.chat_messages.append({"role": "assistant", "content": result})
                console.print(f"\n[bold]Agent:[/bold] {result}\n")
            except Exception as e:
                _handle_error(e, ctx.obj.get("verbose", False))
    except KeyboardInterrupt:
        pass

    # Save session on exit
    if session.chat_messages:
        from .history import extract_title
        if session.title == "Untitled":
            session.title = extract_title(session.chat_messages)
        session.agent_messages = agent.messages
        session.agent_context = agent.context
        save_session(session)
        console.print(f"\n[yellow]Session saved ({session.session_id}).[/yellow]")

    console.print("\n[yellow]Chat session ended.[/yellow]")


@cli.command()
@click.option("--port", "-p", type=int, default=7860, help="Port for the web UI")
@click.option("--host", "-h", type=str, default="127.0.0.1", help="Host to bind (0.0.0.0 for LAN access)")
@click.option("--share", is_flag=True, help="Create a public Gradio link")
def ui(port: int, host: str, share: bool) -> None:
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
    console.print(f"[green]Starting web UI on http://{host}:{port}[/green]")
    launch_app(app, port=port, host=host, share=share)


@cli.command()
@click.option("--configs", "-c", multiple=True, required=True, type=click.Path(exists=True))
@click.option("--stop-on-failure/--no-stop-on-failure", default=True)
@click.pass_context
def batch(ctx: click.Context, configs: tuple[str, ...], stop_on_failure: bool) -> None:
    """Run multiple SeaTunnel configs sequentially."""
    from .tools import execute_tool
    from .config import load_settings

    if ctx.obj.get("model"):
        os.environ["MODEL_NAME"] = ctx.obj["model"]
    if ctx.obj.get("provider"):
        os.environ["LLM_PROVIDER"] = ctx.obj["provider"]

    settings = load_settings()
    result = execute_tool(
        "run_batch",
        {"config_paths": list(configs), "stop_on_failure": stop_on_failure},
        settings,
    )
    console.print(result)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_agent(model: str | None = None, provider: str | None = None):
    from .config import load_settings
    from .agent import SeaTunnelAgent

    if model:
        os.environ["MODEL_NAME"] = model
    if provider:
        os.environ["LLM_PROVIDER"] = provider

    settings = load_settings()
    return SeaTunnelAgent(settings)


def _run_command(
    fn,
    *,
    label: str,
    output: str | None,
    verbose: bool,
) -> None:
    try:
        result = fn()
        console.print(f"\n[bold]{label}:[/bold]\n{result}")
        if output:
            _write_output(output, result)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        _handle_error(e, verbose)


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
