from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from ..common.cli_common import _handle_error, _write_output, console


@click.command()
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


@click.command()
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


@click.command()
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


@click.command()
@click.option("--resume", "-r", default=None, help="Resume session by ID")
@click.option("--list-sessions", is_flag=True, help="List recent sessions and exit")
@click.pass_context
def chat(ctx: click.Context, resume: str | None, list_sessions: bool) -> None:
    """Start an interactive multi-turn chat session with the Agent."""
    from ..common.history import (
        Session,
        load_session,
        new_session_id,
        now_iso,
        save_session,
    )
    from ..common.history import list_sessions as _list_sessions

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
                console.print("\n[bold]Agent:[/bold]")
                console.print(result, markup=False)
                console.print("")
            except Exception as e:
                _handle_error(e, ctx.obj.get("verbose", False))
    except KeyboardInterrupt:
        pass

    # Save session on exit
    if session.chat_messages:
        from ..common.history import extract_title
        if session.title == "Untitled":
            session.title = extract_title(session.chat_messages)
        session.agent_messages = agent.messages
        session.agent_context = agent.context
        save_session(session)
        console.print(f"\n[yellow]Session saved ({session.session_id}).[/yellow]")

    console.print("\n[yellow]Chat session ended.[/yellow]")


def _hash_frontend_paths(paths: list[Path], base: Path) -> str:
    """Content digest over the given files/directories (mtime/git independent).

    Each file contributes its POSIX-style path relative to ``base`` plus its
    content, with unambiguous framing (NUL separator + content length prefix),
    so renames/moves of identical content change the digest.
    """
    import hashlib

    digest = hashlib.sha256()
    files: list[Path] = []
    for p in paths:
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(f for f in p.rglob("*") if f.is_file())
    for f in sorted(files, key=lambda f: f.relative_to(base).as_posix()):
        rel = f.relative_to(base).as_posix()
        data = f.read_bytes()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _build_frontends(
    frontend: Path | None = None, force: bool = False, jobs: int | None = None
) -> None:
    """Incrementally build React workspaces under frontend/ (npm install first if needed).

    Each workspace's sources/build config plus the shared package sources are
    content-hashed and compared with ``<workspace>/dist/.build-hash``; unchanged
    workspaces are skipped unless ``force`` is set. Workspaces needing a rebuild
    run in a bounded thread pool of ``jobs`` workers (default ``min(CPU, 6)``),
    each build's output flushed as one ``[name]``-prefixed block; any failure
    makes the whole run exit non-zero after listing all failed workspaces.
    """
    import json
    import os
    import shutil
    import subprocess
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if jobs is None:
        jobs = min(os.cpu_count() or 1, 6)

    if frontend is None:
        frontend = Path(__file__).resolve().parents[3] / "frontend"
    if not (frontend / "package.json").is_file():
        console.print(f"[red]frontend/ not found at {frontend}; skipping build.[/red]")
        sys.exit(1)
    npm = shutil.which("npm")
    if npm is None:
        console.print("[red]npm not found on PATH; cannot build frontends.[/red]")
        sys.exit(1)
    if not (frontend / "node_modules").is_dir():
        console.print("[yellow]node_modules missing — running npm install...[/yellow]")
        subprocess.run([npm, "install"], cwd=frontend, check=True)

    workspaces: list[str] = json.loads((frontend / "package.json").read_text("utf-8")).get(
        "workspaces", []
    )
    shared_hash = _hash_frontend_paths(
        [
            p
            for p in (frontend / "shared").iterdir()
            if p.name not in ("node_modules", "dist")
            and not p.name.endswith(".tsbuildinfo")
        ]
        if (frontend / "shared").is_dir()
        else [],
        base=frontend,
    )

    pending: list[tuple[str, str]] = []  # (workspace name, its content hash)
    for name in workspaces:
        ws = frontend / name
        pkg_file = ws / "package.json"
        if not pkg_file.is_file():
            continue
        if "build" not in json.loads(pkg_file.read_text("utf-8")).get("scripts", {}):
            continue  # no build script (e.g. shared)
        inputs = [ws / "src", pkg_file, ws / "vite.config.ts"]
        inputs.extend(ws.glob("tsconfig*"))
        ws_hash = _hash_frontend_paths(inputs, base=frontend) + ":" + shared_hash
        hash_file = ws / "dist" / ".build-hash"
        if (
            not force
            and (ws / "dist").is_dir()
            and hash_file.is_file()
            and hash_file.read_text("utf-8").strip() == ws_hash
        ):
            console.print(f"[cyan]{name}: skipped (unchanged)[/cyan]")
            continue
        pending.append((name, ws_hash))

    def build_one(name: str) -> tuple[str, int, str]:
        proc = subprocess.run(
            [npm, "run", "build", "--workspace", name],
            cwd=frontend,
            capture_output=True,
            text=True,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return name, proc.returncode, output

    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(build_one, name): name for name, _ in pending}
        hashes = dict(pending)
        for future in as_completed(futures):
            name, returncode, output = future.result()
            ws = frontend / name
            block = "".join(f"[{name}] {line}\n" for line in output.splitlines())
            console.print(
                f"[green]{name}: building (npm run build --workspace {name})...[/green]"
            )
            if block:
                console.print(block, end="", markup=False, highlight=False)
            if returncode != 0:
                console.print(f"[red]{name}: build failed (exit {returncode})[/red]")
                failed.append(name)
                continue
            if not (ws / "dist").is_dir():
                console.print(
                    f"[yellow]{name}: build produced no dist/ — "
                    "not writing .build-hash (will rebuild next time)[/yellow]"
                )
                continue
            (ws / "dist" / ".build-hash").write_text(hashes[name], encoding="utf-8")
            console.print(f"[green]{name}: built[/green]")

    if failed:
        console.print(f"[red]frontend build failed for: {', '.join(sorted(failed))}[/red]")
        sys.exit(1)


@click.command()
@click.option("--port", "-p", type=int, default=7860, help="Port for the web UI")
@click.option("--host", "-h", type=str, default="127.0.0.1", help="Host to bind (0.0.0.0 for LAN access)")
@click.option("--share", is_flag=True, help="Create a public Gradio link")
@click.option("--api", is_flag=True, help="Enable REST API endpoints (/api/text2sql/, /api/sql_review/, /api/lineage/, /api/transpile/, /api/skew/)")
@click.option("--insecure", is_flag=True, help="Allow a non-loopback/share launch without SEATUNNEL_UI_AUTH (not recommended)")
@click.option("--build", "build_frontend", is_flag=True, help="Build the React frontends (npm run build) before launching; unchanged workspaces are skipped")
@click.option("--force", is_flag=True, help="With --build: rebuild all workspaces, ignoring the incremental cache")
def ui(port: int, host: str, share: bool, api: bool, insecure: bool, build_frontend: bool, force: bool) -> None:
    """Launch the Gradio web UI for interactive agent use."""
    if build_frontend:
        _build_frontends(force=force)
    elif force:
        console.print("[yellow]--force has no effect without --build[/yellow]")
    try:
        from ..hub.ui import create_ui, launch_app
    except ModuleNotFoundError as exc:
        # only a missing gradio means "not installed" — anything else
        # (e.g. a broken internal import) must surface, not be masked
        if exc.name is None or not exc.name.startswith("gradio"):
            raise
        console.print(
            "[red]Gradio is not installed.[/red]\n"
            'Install it with: pip install "seatunnel-agent[ui]"'
        )
        sys.exit(1)

    app = create_ui()
    if api:
        console.print(f"[green]REST API enabled at http://{host}:{port}/api/text2sql/[/green]")
    console.print(f"[green]Starting web UI on http://{host}:{port}[/green]")
    launch_app(app, port=port, host=host, share=share, api=api, insecure=insecure)


@click.command()
@click.option("--configs", "-c", multiple=True, required=True, type=click.Path(exists=True))
@click.option("--stop-on-failure/--no-stop-on-failure", default=True)
@click.pass_context
def batch(ctx: click.Context, configs: tuple[str, ...], stop_on_failure: bool) -> None:
    """Run multiple SeaTunnel configs sequentially."""
    from seatunnel_agent.agents.data.seatunnel.tools import execute_tool

    from ..common.config import load_settings

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


def _make_agent(model: str | None = None, provider: str | None = None):
    from seatunnel_agent.agents.data.seatunnel.agent import SeaTunnelAgent

    from ..common.config import load_settings

    old_model = os.environ.get("MODEL_NAME")
    old_provider = os.environ.get("LLM_PROVIDER")
    try:
        if model:
            os.environ["MODEL_NAME"] = model
        if provider:
            os.environ["LLM_PROVIDER"] = provider
        settings = load_settings()
    finally:
        if model:
            if old_model is None:
                os.environ.pop("MODEL_NAME", None)
            else:
                os.environ["MODEL_NAME"] = old_model
        if provider:
            if old_provider is None:
                os.environ.pop("LLM_PROVIDER", None)
            else:
                os.environ["LLM_PROVIDER"] = old_provider
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
        console.print(f"\n[bold]{label}:[/bold]")
        console.print(result, markup=False)
        if output:
            _write_output(output, result)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        _handle_error(e, verbose)


def register(cli) -> None:
    cli.add_command(run)
    cli.add_command(validate)
    cli.add_command(diagnose)
    cli.add_command(chat)
    cli.add_command(ui)
    cli.add_command(batch)
