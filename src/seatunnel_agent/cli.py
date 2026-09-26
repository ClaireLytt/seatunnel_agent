from __future__ import annotations

import os
import sys

import click
from rich.console import Console

from . import __version__
from .sql_review.linter import DIALECTS as REVIEW_DIALECTS
from .sql_transpile import DIALECTS as TRANSPILE_DIALECTS

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
                console.print("\n[bold]Agent:[/bold]")
                console.print(result, markup=False)
                console.print("")
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
@click.option("--api", is_flag=True, help="Enable REST API endpoints (/api/text2sql/, /api/sql_review/, /api/lineage/, /api/transpile/)")
def ui(port: int, host: str, share: bool, api: bool) -> None:
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
    if api:
        console.print(f"[green]REST API enabled at http://{host}:{port}/api/text2sql/[/green]")
    console.print(f"[green]Starting web UI on http://{host}:{port}[/green]")
    launch_app(app, port=port, host=host, share=share, api=api)


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


@cli.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--file", "-f", "sql_file", type=click.Path(exists=True), default=None,
              help="SQL file to review")
@click.option("--sql", "-s", type=str, default=None, help="SQL text to review")
@click.option("--dir", "-D", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="Review every *.sql file under a directory (recursive)")
@click.option("--diff", is_flag=True,
              help="Review *.sql files changed vs git base (see --diff-base)")
@click.option("--diff-base", type=str, default="HEAD",
              help="Git ref to diff against (default: HEAD)")
@click.option("--dialect", "-d", type=click.Choice(list(REVIEW_DIALECTS)),
              default="hive", help="SQL dialect")
@click.option("--static-only", is_flag=True,
              help="Run only the deterministic linter (no LLM, no API key needed)")
@click.option("--ddl", type=click.Path(exists=True), default=None,
              help="Optional DDL file for schema-aware review")
@click.option("--db", type=str, default=None,
              help="Pull schemas from a live database: host:port/database")
@click.option("--db-user", type=str, default=None, help="Database username")
@click.option("--db-password", type=str, default=None, help="Database password")
@click.option("--rules", type=click.Path(exists=True), default=None,
              help="Rule config file (default: auto-discover .sqlreview.yaml in cwd)")
@click.option("--fail-on", type=click.Choice(["critical", "risk", "suggestion"]),
              default=None, help="Exit 1 when findings at/above this severity exist (CI gate)")
@click.option("--fix", is_flag=True,
              help="Use the LLM to generate fixed SQL for findings (needs API key)")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json", "sarif"]),
              default="markdown", help="Report format (json/sarif for machines/CI)")
@click.option("--baseline", type=click.Path(), default=None,
              help="Baseline file: suppress known findings, only report new ones")
@click.option("--update-baseline", is_flag=True,
              help="Record current findings into the baseline file and exit")
@click.option("--no-cache", is_flag=True,
              help="Skip the LLM review cache (always call the LLM afresh)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
@click.pass_context
def review(
    ctx: click.Context,
    paths: tuple[str, ...],
    sql_file: str | None,
    sql: str | None,
    directory: str | None,
    diff: bool,
    diff_base: str,
    dialect: str,
    static_only: bool,
    ddl: str | None,
    db: str | None,
    db_user: str | None,
    db_password: str | None,
    rules: str | None,
    fail_on: str | None,
    fix: bool,
    fmt: str,
    baseline: str | None,
    update_baseline: bool,
    no_cache: bool,
    output: str | None,
) -> None:
    """SQL Code Review — static analysis + LLM review, no execution needed.

    PATHS: optional *.sql files or directories (as passed by pre-commit)."""
    import re
    import time
    from pathlib import Path

    from .sql_review import load_review_config

    verbose = ctx.obj.get("verbose", False)

    # ── collect review targets ──
    sources: list[tuple[str, str]] = []
    try:
        if sql:
            sources.append(("<inline>", sql))
        if sql_file:
            sources.append((sql_file, Path(sql_file).read_text(encoding="utf-8")))
        if paths or directory:
            from .sql_review.runner import collect_sql_files
        for raw in paths:
            p = Path(raw)
            if p.is_dir():
                for f in collect_sql_files(p):
                    sources.append((str(f), f.read_text(encoding="utf-8")))
            else:
                sources.append((str(p), p.read_text(encoding="utf-8")))
        if directory:
            for p in collect_sql_files(directory):
                sources.append((str(p), p.read_text(encoding="utf-8")))
        if diff:
            from .sql_review.runner import changed_sql_files
            for p in changed_sql_files(diff_base):
                sources.append((str(p), p.read_text(encoding="utf-8")))
    except (OSError, RuntimeError) as e:
        console.print(f"[red]收集审查目标失败:[/red] {e}")
        sys.exit(1)
    seen_labels: set[str] = set()
    sources = [
        (label, text) for label, text in sources
        if not (label in seen_labels or seen_labels.add(label))
    ]
    if not sources:
        raise click.UsageError(
            "Provide SQL via --sql / --file / --dir / --diff or positional paths"
        )

    machine = fmt in ("json", "sarif")

    # ── rule config (.sqlreview.yaml) ──
    try:
        review_config = load_review_config(rules)
    except ValueError as e:
        raise click.UsageError(str(e))
    if review_config.source_path and not machine:
        console.print(f"[dim]规则配置: {review_config.source_path}[/dim]")
    fail_on = fail_on or review_config.fail_on

    # ── baseline (suppress known findings) ──
    baseline_prints: set[str] = set()
    if baseline and not update_baseline:
        from .sql_review.baseline import load_baseline
        try:
            baseline_prints = load_baseline(baseline)
        except ValueError as e:
            raise click.UsageError(str(e))

    # ── schema store (--ddl and/or --db) ──
    store = None
    db_executor = None
    if ddl:
        from .text2sql.schema import SchemaStore
        store = SchemaStore.from_file(ddl)
    if db:
        m = re.fullmatch(r"([\w.\-]+):(\d+)/([\w.\-]+)", db.strip())
        if not m:
            raise click.UsageError("--db 格式应为 host:port/database")
        from .sql_review.linter import EXECUTOR_DS_TYPES
        from .text2sql.executor import DatabaseConfig, create_executor
        from .text2sql.schema import SchemaStore
        ds_type = EXECUTOR_DS_TYPES.get(dialect)
        if ds_type is None:
            click.echo(
                f"Warning: dialect '{dialect}' has no dedicated database executor — "
                "falling back to the hive executor for schema fetching.",
                err=True,
            )
            ds_type = "hive"
        try:
            db_config = DatabaseConfig(
                ds_type=ds_type,
                host=m.group(1), port=int(m.group(2)), database=m.group(3),
                username=db_user, password=db_password,
            )
            db_executor = create_executor(db_config)
            db_store = SchemaStore.from_db(db_executor)
        except Exception as e:
            console.print(f"[red]数据库 schema 拉取失败:[/red] {e}")
            if verbose:
                console.print_exception()
            sys.exit(1)
        if store is None:
            store = db_store
        else:
            for t in db_store.tables:
                store.add(t)

    # ── LLM settings (agent mode; static --fix is deterministic, no LLM) ──
    settings = None
    if not static_only:
        from .config import load_settings
        if ctx.obj.get("model"):
            os.environ["MODEL_NAME"] = ctx.obj["model"]
        if ctx.obj.get("provider"):
            os.environ["LLM_PROVIDER"] = ctx.obj["provider"]
        settings = load_settings()

    # ── review loop ──
    from .sql_review import Severity, render_report, static_review_report
    from .sql_review.rlog import ReviewLogger

    logger = ReviewLogger()
    all_findings = []
    rendered: list[tuple[str, str]] = []
    reports = []
    baseline_entries = []
    per_file: list[tuple[str, int, int, int]] = []
    failed: list[str] = []
    multi = len(sources) > 1

    for label, text in sources:
        start = time.time()
        try:
            if static_only:
                rep = static_review_report(text, dialect, store=store, config=review_config)
                report_md = render_report(rep)
            else:
                from .sql_review import SQLReviewAgent
                agent = SQLReviewAgent(
                    settings, dialect=dialect, store=store, config=review_config,
                    use_cache=not no_cache,
                )
                report_md = agent.review(text)
                rep = agent.runtime.report if agent.runtime else None
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user.[/yellow]")
            sys.exit(130)
        except Exception as e:
            if multi:
                console.print(f"\n[red]审查 {label} 失败:[/red]")
            _handle_error(e, verbose)
            failed.append(label)
            if not multi:
                sys.exit(1)
            continue

        # ── EXPLAIN verification (live DB + OLTP dialect only) ──
        if rep and db_executor is not None:
            from .sql_review.explain import verify_with_explain
            verified = verify_with_explain(rep.findings, text, dialect, db_executor)
            if verified != rep.findings:
                rep.findings = verified
                report_md = render_report(rep)

        findings = rep.findings if rep else []
        baseline_entries.extend((label, f) for f in findings)

        suppressed = 0
        if baseline_prints and rep:
            from .sql_review.baseline import split_by_baseline
            new, known = split_by_baseline(label, findings, baseline_prints)
            if known:
                rep.findings = new
                findings = new
                suppressed = len(known)
                report_md = render_report(rep)

        stats = rep.stats() if rep else {}
        logger.log(
            sql=text, dialect=dialect,
            mode="static" if static_only else "agent",
            findings=findings, stats=stats, target=label,
            elapsed_ms=int((time.time() - start) * 1000),
        )
        all_findings.extend(findings)
        rendered.append((label, report_md))
        if rep:
            reports.append((label, rep))
        elif machine:
            # agent mode may not yield a structured report; emit an empty
            # entry so json/sarif output still accounts for every source
            from .sql_review import ReviewReport
            reports.append((label, ReviewReport(dialect=dialect)))
        per_file.append((
            label,
            sum(1 for f in findings if f.severity is Severity.CRITICAL),
            sum(1 for f in findings if f.severity is Severity.RISK),
            sum(1 for f in findings if f.severity is Severity.SUGGESTION),
        ))

        if not machine:
            if multi:
                console.print(f"\n[bold cyan]=== {label} ===[/bold cyan]")
            if suppressed:
                console.print(f"[dim]基线抑制 {suppressed} 条已知问题[/dim]")
            console.print("\n[bold]CR report:[/bold]")
            console.print(report_md, markup=False)

        if fix and findings:
            fixed_sql = None
            if static_only:
                from .sql_review.autofix import apply_static_fixes, describe_fixes
                fixed_sql, applied = apply_static_fixes(
                    text, dialect, config=review_config)
                if not applied:
                    fixed_sql = None
                    click.echo(
                        "没有可静态自动修复的问题；其余问题需去掉 --static-only "
                        "用 LLM 修复", err=True)
                elif not machine:
                    console.print(f"\n[bold green]静态修复（{len(applied)} 处）:"
                                  f"[/bold green]\n{describe_fixes(applied)}")
            else:
                from .sql_review.fixer import generate_fix
                try:
                    fixed_sql = generate_fix(settings, text, dialect, report_md)
                except Exception as e:
                    # stderr: must not pollute --format json/sarif stdout
                    click.echo(f"生成修复 SQL 失败: {e}", err=True)
            if fixed_sql is not None:
                if not machine:
                    console.print("\n[bold green]修复后 SQL:[/bold green]")
                    console.print(fixed_sql, markup=False)
                if label != "<inline>":
                    fixed_path = Path(label).with_suffix(".fixed.sql")
                    fixed_path.write_text(fixed_sql + "\n", encoding="utf-8")
                    if not machine:
                        console.print(f"[dim]已写入 {fixed_path}[/dim]")

    # ── batch summary ──
    if multi and not machine:
        console.print("\n[bold]批量审查汇总:[/bold]")
        for label, crit, risk, sugg in per_file:
            console.print(
                f"  [red]{crit:>3}[/red] / [yellow]{risk:>3}[/yellow] / "
                f"[green]{sugg:>3}[/green]  {label}"
            )
        crit = sum(c for _, c, _r, _s in per_file)
        risk = sum(r for _, _c, r, _s in per_file)
        sugg = sum(s for _, _c, _r, s in per_file)
        console.print(
            f"  共 {len(sources)} 个文件 — "
            f"[red]严重 {crit}[/red] / [yellow]风险 {risk}[/yellow] / [green]建议 {sugg}[/green]"
        )
        if failed:
            console.print(f"  [red]审查失败 {len(failed)} 个: {', '.join(failed)}[/red]")

    # ── machine-readable output (--format json/sarif) ──
    if machine:
        from .sql_review.formats import results_to_json, results_to_sarif
        doc = results_to_json(reports) if fmt == "json" else results_to_sarif(reports)
        if output:
            _write_output(output, doc)
        else:
            click.echo(doc)
    elif output:
        combined = "\n\n---\n\n".join(
            (f"# {label}\n\n{md}" if multi else md) for label, md in rendered
        )
        _write_output(output, combined)

    # ── baseline update ──
    if update_baseline:
        from .sql_review.baseline import DEFAULT_BASELINE, save_baseline
        bpath = baseline or DEFAULT_BASELINE
        try:
            n = save_baseline(bpath, baseline_entries)
        except OSError as e:
            click.echo(f"基线写入失败: {e}", err=True)
            sys.exit(1)
        if not machine:
            console.print(f"[green]基线已更新: {bpath}（{n} 条指纹）[/green]")
        if failed:
            sys.exit(1)
        return

    # ── CI gate ──
    if fail_on:
        from .sql_review.runner import severity_reached
        if severity_reached(all_findings, fail_on):
            console.print(f"\n[red]存在 {fail_on} 及以上级别的问题，审查未通过。[/red]")
            sys.exit(1)
    if failed:
        sys.exit(1)


@cli.command(name="review-harness")
@click.option("--log", "log_path", type=click.Path(exists=True),
              default=None,
              help="Text2SQL query log (default: logs/text2sql_queries.jsonl)")
@click.option("--dialect", "-d",
              type=click.Choice(list(REVIEW_DIALECTS)),
              default="hive", help="SQL dialect for the linter")
@click.option("--limit", "-n", type=int, default=None,
              help="Only replay the most recent N log records")
@click.option("--ddl", type=click.Path(exists=True), default=None,
              help="Optional DDL file for schema-aware review")
@click.option("--rules", type=click.Path(exists=True), default=None,
              help="Rule config file (default: auto-discover .sqlreview.yaml)")
@click.option("--lang", type=click.Choice(["en", "zh"]), default="zh",
              help="Report language")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Output format")
@click.option("--fail-on", type=click.Choice(["critical", "risk", "suggestion"]),
              default=None,
              help="Exit 1 when findings at/above this severity exist (CI gate)")
@click.option("--baseline", type=click.Path(exists=True), default=None,
              help="Previous run's JSON report (-F json -o ...) to diff against")
@click.option("--llm-cache", "llm_cache_flag", is_flag=True, default=False,
              help="Replay cached LLM reviews (logs/sql_review.jsonl) for "
                   "matching SQL")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
def review_harness(
    log_path: str | None,
    dialect: str,
    limit: int | None,
    ddl: str | None,
    rules: str | None,
    lang: str,
    fmt: str,
    fail_on: str | None,
    baseline: str | None,
    llm_cache_flag: bool,
    output: str | None,
) -> None:
    """Replay Text2SQL query logs through the static reviewer.

    Every generated SQL in logs/text2sql_queries.jsonl is linted and the
    results are aggregated — a regression harness tying Text2SQL output
    to the SQL Review rules. No LLM, no database connection needed."""
    import json as _json
    from pathlib import Path

    from .sql_review import load_review_config
    from .sql_review.harness import (
        DEFAULT_LOG, diff_against_baseline, load_llm_cache,
        render_harness_report, run_harness,
    )

    try:
        review_config = load_review_config(rules)
    except ValueError as e:
        raise click.UsageError(str(e))

    store = None
    if ddl:
        from .text2sql.schema import SchemaStore, parse_ddl
        tables = parse_ddl(Path(ddl).read_text(encoding="utf-8"))
        store = SchemaStore(tables) if tables else None

    llm_cache = load_llm_cache() if llm_cache_flag else None

    try:
        result = run_harness(
            log_path or DEFAULT_LOG, dialect=dialect, limit=limit,
            store=store, config=review_config, llm_cache=llm_cache,
        )
    except FileNotFoundError as e:
        raise click.UsageError(str(e))

    baseline_diff = None
    if baseline:
        try:
            baseline_doc = _json.loads(
                Path(baseline).read_text(encoding="utf-8"))
            if not isinstance(baseline_doc, dict):
                raise ValueError("baseline must be a JSON object")
        except (ValueError, OSError) as e:
            raise click.UsageError(f"invalid baseline file: {e}")
        baseline_diff = diff_against_baseline(baseline_doc, result)

    if fmt == "json":
        payload = result.to_dict()
        if baseline_diff is not None:
            payload["baseline_diff"] = baseline_diff
        doc = _json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        doc = render_harness_report(result, lang=lang,
                                    baseline_diff=baseline_diff)
    if output:
        _write_output(output, doc)
    else:
        click.echo(doc)

    if fail_on:
        counts = {"critical": result.criticals,
                  "risk": result.criticals + result.risks,
                  "suggestion": result.criticals + result.risks
                  + result.suggestions}
        if counts.get(fail_on, 0) > 0:
            console.print(
                f"\n[red]存在 {fail_on} 及以上级别的问题，harness 未通过。[/red]")
            sys.exit(1)


@cli.command(name="review-stats")
@click.option("--recent", "-n", type=int, default=None,
              help="Only aggregate the most recent N reviews")
def review_stats(recent: int | None) -> None:
    """Show SQL review history statistics (from logs/sql_review.jsonl)."""
    from .sql_review.rlog import ReviewLogger

    summary = ReviewLogger().summarize(recent)
    if not summary["reviews"]:
        console.print("[yellow]还没有审查历史记录。[/yellow]")
        return
    console.print("[bold]SQL Review 历史统计[/bold]")
    console.print(f"  审查次数: {summary['reviews']}")
    console.print(f"  发现问题总数: {summary['findings']}")
    sev = summary["severities"]
    console.print(
        f"  严重: {sev.get('critical', 0)}  风险: {sev.get('risk', 0)}  "
        f"建议: {sev.get('suggestion', 0)}"
    )
    if summary["top_categories"]:
        console.print("  高频问题类别:")
        for item in summary["top_categories"]:
            console.print(f"    {item['count']:>4}  {item['label']} ({item['category']})")


@cli.command()
@click.option("--table", "-t", type=str, default=None,
              help="目标表（如 zz.dwm_orders_df）")
@click.option("--direction", type=click.Choice(["up", "down", "both"]),
              default="both", help="血缘方向：up=上游 down=下游 both=全链路")
@click.option("--depth", type=int, default=3, help="遍历深度（默认 3）")
@click.option("--column", "-c", type=str, default=None,
              help="字段级影响分析：改这个字段影响哪些下游")
@click.option("--path-to", type=str, default=None,
              help="路径查询：--table 到该表的最短血缘路径")
@click.option("--sla-delay", type=float, default=None,
              help="SLA 影响分析：假设 --table 延迟 N 小时，列出受影响 SLA/基线任务")
@click.option("--check", "health", is_flag=True,
              help="治理体检：环依赖 / 孤立表 / 无下游可下线表")
@click.option("--sql-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="从目录下的 *.sql 文件构建血缘图（递归）")
@click.option("--sql-dialect", type=click.Choice(
                  ["hive", "spark", "flink", "maxcompute", "mysql",
                   "postgresql", "clickhouse", "doris", "starrocks", "sqlite"]),
              default="hive", show_default=True,
              help="解析 --sql-dir 脚本用的 SQL 方言（影响字段级血缘的 AST 解析）")
@click.option("--seatunnel-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="从目录下的 SeaTunnel 配置（*.conf/*.config/*.json）构建 source→sink 血缘")
@click.option("--hive", "use_hive", is_flag=True,
              help="从 Hive 元数据血缘表构建（需 .env 配置 HIVE_HOST 等）")
@click.option("--meta-table", type=str, default=None,
              help="血缘元数据表名（默认 zz.dwm_meta_table_lineage_df）")
@click.option("--partition", type=str, default=None,
              help="指定 pt 分区（默认自动取最新分区）")
@click.option("--no-cache", "no_cache", is_flag=True,
              help="跳过 Hive 血缘图的本地 TTL 缓存，强制重新查询")
@click.option("--agent", "use_agent", is_flag=True,
              help="Agent 模式：用自然语言提问（需 API key，配合 --ask）")
@click.option("--ask", type=str, default=None,
              help="自然语言血缘问题（隐含 --agent）")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "mermaid", "json"]),
              default="markdown", help="输出格式")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
@click.option("--export-openlineage", "export_ol", type=click.Path(), default=None,
              help="把整张血缘图导出为 OpenLineage RunEvent JSON 文件")
@click.pass_context
def lineage(
    ctx: click.Context,
    table: str | None,
    direction: str,
    depth: int,
    column: str | None,
    path_to: str | None,
    sla_delay: float | None,
    health: bool,
    sql_dir: str | None,
    sql_dialect: str,
    seatunnel_dir: str | None,
    use_hive: bool,
    meta_table: str | None,
    partition: str | None,
    no_cache: bool,
    use_agent: bool,
    ask: str | None,
    fmt: str,
    output: str | None,
    export_ol: str | None,
) -> None:
    """数据表全链路血缘分析 — 上下游链路 / 字段影响 / SLA 与基线。"""
    import time

    verbose = ctx.obj.get("verbose", False)
    if not sql_dir and not seatunnel_dir and not use_hive:
        raise click.UsageError("至少指定一个血缘来源：--sql-dir / --seatunnel-dir / --hive")
    if ask:
        use_agent = True
    if use_agent and not ask:
        raise click.UsageError("--agent 模式需要 --ask 提供问题")
    if not use_agent and not table and not health and not export_ol:
        raise click.UsageError("请用 --table 指定目标表（或 --ask 用自然语言提问 / --check 治理体检）")

    from .data_lineage import LineageLogger, build_graph, load_lineage_config

    config = load_lineage_config()
    if meta_table:
        import dataclasses
        config = dataclasses.replace(config, meta_table=meta_table)

    start = time.time()
    try:
        graph, warnings = build_graph(
            sql_dir=sql_dir, use_hive=use_hive,
            meta_table=config.meta_table, partition=partition,
            seatunnel_dir=seatunnel_dir, use_cache=not no_cache,
            sql_dialect=sql_dialect,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        _handle_error(e, verbose)
        return
    for w in warnings:
        console.print(f"[yellow]警告:[/yellow] {w}")
    stats = graph.stats()
    console.print(
        f"[dim]血缘图: {stats.get('tables', 0)} 表 / {stats.get('edges', 0)} 边 / "
        f"{stats.get('column_edges', 0)} 字段边[/dim]"
    )

    logger = LineageLogger()

    if export_ol:
        from .data_lineage.openlineage import export_openlineage_file

        try:
            out_path = export_openlineage_file(graph, export_ol)
        except OSError as e:
            _handle_error(e, verbose)
            return
        console.print(f"[green]OpenLineage 事件已导出:[/green] {out_path}")
        if not use_agent and not table and not health:
            return

    # ── agent mode ──
    if use_agent:
        from .config import load_settings
        from .data_lineage import LineageAgent

        if ctx.obj.get("model"):
            os.environ["MODEL_NAME"] = ctx.obj["model"]
        if ctx.obj.get("provider"):
            os.environ["LLM_PROVIDER"] = ctx.obj["provider"]
        settings = load_settings()
        agent = LineageAgent(
            settings, graph=graph, config=config, sql_dir=sql_dir,
            sql_dialect=sql_dialect,
            seatunnel_dir=seatunnel_dir,
            hive_available=use_hive, meta_table=config.meta_table,
            partition=partition,
        )
        try:
            answer = agent.analyze(ask)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user.[/yellow]")
            sys.exit(130)
        except Exception as e:
            _handle_error(e, verbose)
            return
        logger.log(
            query=ask, direction=direction, mode="agent",
            graph_stats=stats, elapsed_ms=int((time.time() - start) * 1000),
        )
        console.print("\n[bold]血缘分析:[/bold]")
        console.print(answer, markup=False)
        if output:
            _write_output(output, answer)
        return

    # ── deterministic mode ──
    from .data_lineage import render_report, static_lineage
    from .data_lineage.render import (
        render_health,
        render_path,
        render_path_mermaid,
        render_sla_impact,
    )

    def _finish(content: str, mode: str) -> None:
        logger.log(
            query=table or mode, direction=direction, mode=mode,
            graph_stats=stats, elapsed_ms=int((time.time() - start) * 1000),
        )
        if output:
            _write_output(output, content)
        else:
            console.print(content)

    if health:
        report_hc = graph.health_check()
        if fmt == "json":
            import json as _json
            content = _json.dumps(report_hc.to_dict(), ensure_ascii=False,
                                  indent=2, default=str)
        else:
            content = render_health(report_hc)
        _finish(content, "health")
        return

    if path_to:
        path = graph.path_between(table, path_to)
        if fmt == "mermaid":
            content = render_path_mermaid(path, graph)
        elif fmt == "json":
            import json as _json
            content = _json.dumps(
                {"src": table, "dst": path_to, "found": path is not None,
                 "path": path or []},
                ensure_ascii=False, indent=2,
            )
        else:
            content = render_path(path, table, path_to, graph)
        _finish(content, "path")
        return

    if sla_delay is not None:
        impact = graph.sla_impact(table, sla_delay, depth=config.max_depth,
                                  max_nodes=config.max_nodes)
        if impact.missing_root:
            console.print(f"[red]未在血缘图中找到表 `{table}`。[/red]")
            sys.exit(1)
        if fmt == "json":
            import json as _json
            content = _json.dumps(impact.to_dict(), ensure_ascii=False,
                                  indent=2, default=str)
        else:
            content = render_sla_impact(impact)
        _finish(content, "sla")
        return

    dir_map = {"up": "upstream", "down": "downstream", "both": "both"}
    report = static_lineage(
        graph, table, dir_map[direction], depth, column=column, config=config
    )
    chain = report.chain
    logger.log(
        query=table, direction=direction, mode="static",
        graph_stats=stats,
        chain_stats={
            "upstream": chain.upstream_count if chain else 0,
            "downstream": chain.downstream_count if chain else 0,
        },
        elapsed_ms=int((time.time() - start) * 1000),
    )

    if chain and chain.missing_root:
        console.print(f"[red]未在血缘图中找到表 `{table}`。[/red]")
        suggestions = graph.search(table.rsplit(".", 1)[-1])
        if suggestions:
            console.print("[yellow]相近的表:[/yellow]")
            for node in suggestions[:10]:
                console.print(f"  - {node.name}")
        sys.exit(1)

    if fmt == "mermaid":
        content = report.mermaid
    elif fmt == "json":
        import json as _json
        content = _json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str)
    else:
        content = render_report(report)

    if output:
        _write_output(output, content)
    else:
        console.print(content)


@cli.command(name="lineage-stats")
@click.option("--recent", "-n", type=int, default=20,
              help="Show the most recent N lineage queries")
def lineage_stats(recent: int) -> None:
    """Show lineage query history (from logs/lineage.jsonl)."""
    from .data_lineage import LineageLogger

    records = LineageLogger().recent(recent)
    if not records:
        console.print("[yellow]还没有血缘查询历史记录。[/yellow]")
        return
    console.print("[bold]血缘查询历史[/bold]")
    for r in records:
        chain = r.get("chain_stats") or {}
        console.print(
            f"  {r.get('timestamp', '')}  [{r.get('mode', '')}/{r.get('source', '')}] "
            f"{r.get('query', '')}  方向={r.get('direction', '-') or '-'}  "
            f"上游={chain.get('upstream', '-')} 下游={chain.get('downstream', '-')}"
        )


@cli.command(name="impact-stats")
@click.option("--recent", "-n", type=int, default=20, help="显示最近 N 条")
def impact_stats(recent: int) -> None:
    """变更影响分析历史与治理统计 (logs/impact.jsonl)。"""
    from collections import Counter

    from .data_lineage.impact import ImpactLogger

    records = ImpactLogger().recent(recent)
    if not records:
        console.print("[yellow]还没有变更影响分析记录。[/yellow]")
        return
    console.print("[bold]变更影响分析历史[/bold]")
    for r in records:
        st = r.get("stats") or {}
        console.print(
            f"  {r.get('timestamp', '')}  [{r.get('mode', '')}/{r.get('source', '')}] "
            f"基线={r.get('baseline', '-') or '-'}  "
            f"变更={st.get('changed', 0)} error={st.get('error', 0)} "
            f"warn={st.get('warn', 0)}  最严重={r.get('worst', '-')}")
    worst = Counter(r.get("worst", "clean") for r in records)
    hot = Counter(t for r in records for t in r.get("tables", []))
    console.print(
        f"\n[bold]汇总[/bold] 共 {len(records)} 次 · "
        f"含破坏性 {worst.get('error', 0)} 次 · "
        f"口径漂移 {worst.get('warn', 0)} 次 · 干净 {worst.get('clean', 0)} 次")
    if hot:
        top = " · ".join(f"{t}×{c}" for t, c in hot.most_common(5))
        console.print(f"[bold]高频变更表[/bold] {top}")


@cli.command(name="lineage-mcp")
@click.option("--sql-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="从目录下的 *.sql 文件构建血缘图（递归）")
@click.option("--sql-dialect", type=click.Choice(
                  ["hive", "spark", "flink", "maxcompute", "mysql",
                   "postgresql", "clickhouse", "doris", "starrocks", "sqlite"]),
              default="hive", show_default=True,
              help="解析 --sql-dir 脚本用的 SQL 方言（影响字段级血缘的 AST 解析）")
@click.option("--seatunnel-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="从目录下的 SeaTunnel 配置（*.conf/*.config/*.json）构建 source→sink 血缘")
@click.option("--hive", "use_hive", is_flag=True,
              help="从 Hive 元数据血缘表构建（需 .env 配置 HIVE_HOST 等）")
@click.option("--meta-table", type=str, default=None,
              help="血缘元数据表名（默认 zz.dwm_meta_table_lineage_df）")
@click.option("--partition", type=str, default=None,
              help="指定 pt 分区（默认自动取最新分区）")
def lineage_mcp(
    sql_dir: str | None,
    sql_dialect: str,
    seatunnel_dir: str | None,
    use_hive: bool,
    meta_table: str | None,
    partition: str | None,
) -> None:
    """以 MCP server（stdio）暴露血缘分析工具，供 Claude Desktop 等 MCP 客户端调用。"""
    if not sql_dir and not seatunnel_dir and not use_hive:
        raise click.UsageError("至少指定一个血缘来源：--sql-dir / --seatunnel-dir / --hive")
    from .data_lineage.mcp_server import create_mcp_server

    try:
        server = create_mcp_server(
            sql_dir=sql_dir, seatunnel_dir=seatunnel_dir, use_hive=use_hive,
            meta_table=meta_table, partition=partition, sql_dialect=sql_dialect,
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc))
    server.run()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_agent(model: str | None = None, provider: str | None = None):
    from .config import load_settings
    from .agent import SeaTunnelAgent

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


def _write_output(path: str, content: str) -> None:
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")
    console.print(f"[dim]Result saved to {path}[/dim]")


@cli.command()
@click.option("--sql-dir", "-d", "new_dir", type=click.Path(exists=True, file_okay=False),
              required=True, help="The NEW (current) SQL directory")
@click.option("--old-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="The OLD SQL directory to compare against")
@click.option("--base", "git_base", type=str, default=None,
              help="Git ref for the old state (e.g. HEAD~1, origin/main); "
                   "alternative to --old-dir")
@click.option("--depth", type=int, default=3, help="Downstream walk depth")
@click.option("--sql-dialect", type=str, default="hive",
              help="sqlglot dialect used to parse the SQL files")
@click.option("--format", "-F", "fmt",
              type=click.Choice(["markdown", "json", "md-comment"]),
              default="markdown",
              help="Report format (md-comment = compact PR/MR comment)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              help="Report language")
@click.option("--fail-on", type=click.Choice(["error", "warn"]), default=None,
              help="Exit non-zero when findings at/above this level exist (CI gate)")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save the report to a file")
@click.pass_context
def impact(
    ctx: click.Context,
    new_dir: str,
    old_dir: str | None,
    git_base: str | None,
    depth: int,
    sql_dialect: str,
    fmt: str,
    lang: str,
    fail_on: str | None,
    output: str | None,
) -> None:
    """变更影响分析 — SQL 变更 × 血缘下游遍历，输出上线影响面报告。"""
    import json as _json
    import shutil
    from pathlib import Path

    from .data_lineage.impact import (
        LEVELS, analyze_dirs, impact_to_dict, materialize_git_ref,
        render_impact_comment, render_impact_markdown,
    )

    if bool(old_dir) == bool(git_base):
        raise click.UsageError("Provide exactly one of --old-dir / --base")

    tmp_old: Path | None = None
    try:
        if git_base:
            try:
                tmp_old = materialize_git_ref(git_base, new_dir)
            except RuntimeError as e:
                console.print(f"[red]git 基线模式失败:[/red] {e}")
                console.print("[dim]提示: 非 git 仓库请改用 --old-dir[/dim]")
                sys.exit(1)
            if (tmp_old / ".impact_empty_baseline").exists():
                console.print(
                    f"[yellow]基线 {git_base} 下没有 *.sql —— "
                    "所有文件都将报告为新增[/yellow]")
            old_dir = str(tmp_old)
        try:
            result = analyze_dirs(old_dir, new_dir, depth=depth,
                                  sql_dialect=sql_dialect)
        except ValueError as e:
            raise click.UsageError(str(e))
        if fmt == "json":
            text = _json.dumps(impact_to_dict(result, lang),
                               ensure_ascii=False, indent=2)
            print(text)
        elif fmt == "md-comment":
            text = render_impact_comment(result, lang)
            print(text)
        else:
            text = render_impact_markdown(result, lang)
            console.print(text, markup=False)
        if output:
            Path(output).write_text(text, encoding="utf-8")
            console.print(f"[dim]Report saved to {output}[/dim]")
        from .data_lineage.impact import ImpactLogger
        ImpactLogger().log_impact(
            result, mode="git" if git_base else "dirs", source="cli",
            baseline=git_base or str(old_dir))
        worst = result.worst_level()
        if fail_on and worst and LEVELS.index(worst) <= LEVELS.index(fail_on):
            sys.exit(1)
    finally:
        if tmp_old is not None:
            shutil.rmtree(tmp_old, ignore_errors=True)


@cli.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--sql", "-s", type=str, default=None, help="Inline SQL text to translate")
@click.option("--from", "-f", "src_dialect", type=click.Choice(list(TRANSPILE_DIALECTS)),
              default=None, help="Source dialect (inferred when omitted)")
@click.option("--to", "-t", "dst_dialect", type=click.Choice(list(TRANSPILE_DIALECTS)),
              required=True, help="Target dialect")
@click.option("--dir", "-D", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="Translate every *.sql under this directory")
@click.option("--out", "-o", "out_dir", type=click.Path(), default=None,
              help="Output file (single input) or mirrored output directory (--dir)")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              help="Report language")
@click.option("--no-llm", is_flag=True, help="Skip LLM advice (deterministic only)")
@click.option("--fail-on", type=click.Choice(["error", "warn"]), default=None,
              help="Exit non-zero when findings at/above this level exist (CI gate)")
@click.pass_context
def transpile(
    ctx: click.Context,
    paths: tuple[str, ...],
    sql: str | None,
    src_dialect: str | None,
    dst_dialect: str,
    directory: str | None,
    out_dir: str | None,
    fmt: str,
    lang: str,
    no_llm: bool,
    fail_on: str | None,
) -> None:
    """SQL 方言翻译 — hive/spark/doris/starrocks 互转，输出不兼容点清单。

    PATHS: optional *.sql files to translate."""
    import json as _json
    from pathlib import Path

    from .sql_transpile import (
        batch_to_dict, render_batch_markdown, render_markdown,
        result_to_dict, translate, transpile_dir,
    )
    from .sql_transpile.transpiler import LEVELS

    verbose = ctx.obj.get("verbose", False)
    machine = fmt == "json"

    def _gate(worst: str | None) -> None:
        if fail_on and worst and LEVELS.index(worst) <= LEVELS.index(fail_on):
            sys.exit(1)

    try:
        # ── batch: --dir ──
        if directory:
            batch = transpile_dir(directory, dst=dst_dialect, src=src_dialect,
                                  out_dir=out_dir)
            if machine:
                print(_json.dumps(batch_to_dict(batch, lang),
                                  ensure_ascii=False, indent=2))
            else:
                console.print(render_batch_markdown(batch, lang),
                              markup=False)
            _gate(batch.worst_level())
            return

        # ── single/multi source: --sql / positional files ──
        sources: list[tuple[str, str]] = []
        if sql:
            sources.append(("<inline>", sql))
        for raw in paths:
            p = Path(raw)
            if p.is_dir():
                raise click.UsageError(
                    f"'{raw}' is a directory — use --dir for batch mode")
            sources.append((str(p), p.read_text(encoding="utf-8")))
        if not sources:
            raise click.UsageError(
                "Provide SQL via --sql, positional *.sql files, or --dir")

        worst: str | None = None
        json_out: list[dict] = []
        for label, text in sources:
            result = translate(text, dst=dst_dialect, src=src_dialect)
            w = result.worst_level()
            if w and (worst is None or LEVELS.index(w) < LEVELS.index(worst)):
                worst = w
            if machine:
                json_out.append({"path": label, **result_to_dict(result, lang)})
                continue
            if len(sources) > 1:
                console.print(f"[bold]== {label} ==[/bold]")
            console.print(render_markdown(result, lang), markup=False)
            if out_dir and len(sources) == 1:
                Path(out_dir).write_text(result.output_script(),
                                         encoding="utf-8")
                console.print(f"[dim]Translated SQL saved to {out_dir}[/dim]")
            # LLM advice (single source only; strictly additive)
            if not no_llm and len(sources) == 1:
                try:
                    from .config import load_settings
                    from .sql_transpile.advisor import (
                        advisable_issues, generate_advice)
                    if advisable_issues(result):
                        if ctx.obj.get("model"):
                            os.environ["MODEL_NAME"] = ctx.obj["model"]
                        if ctx.obj.get("provider"):
                            os.environ["LLM_PROVIDER"] = ctx.obj["provider"]
                        settings = load_settings()
                        advice = generate_advice(settings, result, lang)
                        if advice:
                            console.print("\n[bold]LLM 建议 (llm-generated)"
                                          "[/bold]\n" + advice)
                except RuntimeError:
                    pass  # no API key configured — deterministic result stands
        if machine:
            payload = json_out[0] if len(json_out) == 1 else json_out
            print(_json.dumps(payload, ensure_ascii=False, indent=2))
        _gate(worst)
    except ValueError as e:
        raise click.UsageError(str(e))
    except Exception as e:  # noqa: BLE001 — uniform CLI error handling
        _handle_error(e, verbose)


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


if __name__ == "__main__":
    cli()
