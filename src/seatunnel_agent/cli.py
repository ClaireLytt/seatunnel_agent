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
@click.option("--api", is_flag=True, help="Enable REST API endpoints (/api/text2sql/, /api/sql_review/, /api/lineage/, /api/transpile/, /api/skew/)")
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


@cli.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--dir", "-D", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="Migrate every DataX json / sqoop script under this directory")
@click.option("--out", "-o", "out_dir", type=click.Path(), default=None,
              help="Output .conf file (single input) or mirrored directory (--dir)")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh")
@click.option("--fail-on", type=click.Choice(["error", "warn"]), default=None,
              help="Exit non-zero when findings at/above this level exist (CI gate)")
def migrate(
    paths: tuple[str, ...],
    directory: str | None,
    out_dir: str | None,
    fmt: str,
    lang: str,
    fail_on: str | None,
) -> None:
    """DataX/Sqoop → SeaTunnel 配置迁移 — 确定性转换 + 迁移说明清单。

    PATHS: DataX job json / sqoop 命令脚本文件。"""
    import json as _json
    from pathlib import Path

    from .config_migrate import (
        migrate_dir, migrate_file, render_batch_markdown,
        render_migrate_markdown,
    )
    from .config_migrate.migrator import LEVELS as MIG_LEVELS

    def _gate(worst: str | None) -> None:
        if fail_on and worst and MIG_LEVELS.index(worst) <= MIG_LEVELS.index(fail_on):
            sys.exit(1)

    if directory:
        batch = migrate_dir(directory, out_dir=out_dir)
        if fmt == "json":
            print(_json.dumps(batch.to_dict(), ensure_ascii=False, indent=2))
        else:
            console.print(render_batch_markdown(batch, lang), markup=False)
        _gate(batch.worst_level())
        return
    if not paths:
        raise click.UsageError("Provide job files or --dir")
    worst: str | None = None
    for raw in paths:
        res = migrate_file(raw)
        w = res.worst_level()
        if w and (worst is None or MIG_LEVELS.index(w) < MIG_LEVELS.index(worst)):
            worst = w
        if fmt == "json":
            print(_json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
        else:
            console.print(render_migrate_markdown(res, lang), markup=False)
        if out_dir and len(paths) == 1 and res.output_conf:
            Path(out_dir).write_text(res.output_conf, encoding="utf-8")
            console.print(f"[dim]SeaTunnel config saved to {out_dir}[/dim]")
    _gate(worst)


@cli.command(name="datadict")
@click.option("--sql-dir", "-d", type=click.Path(exists=True, file_okay=False),
              required=True, help="从该目录的 *.sql 构建血缘并生成字典")
@click.option("--sql-dialect", type=str, default="hive",
              help="解析 SQL 用的 sqlglot 方言")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh")
@click.option("--describe", is_flag=True,
              help="用 LLM 为每张表补一句描述（明确标注 llm-generated）")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="写出 Markdown 文件（缺省打印到终端）")
@click.pass_context
def datadict(ctx: click.Context, sql_dir: str, sql_dialect: str, lang: str,
             describe: bool, output: str | None) -> None:
    """数据字典生成 — 从 SQL 血缘图输出表/字段/上下游 Markdown 文档。"""
    from pathlib import Path

    from .data_lineage.dictionary import (
        add_llm_descriptions, build_dictionary, render_dictionary_markdown,
    )
    from .data_lineage.loaders import build_graph

    graph, warnings = build_graph(sql_dir=sql_dir, use_cache=False,
                                  sql_dialect=sql_dialect)
    entries = build_dictionary(graph)
    if describe:
        try:
            from .config import load_settings
            filled = add_llm_descriptions(load_settings(), entries, lang)
            console.print(f"[dim]LLM 描述已生成 {filled}/{len(entries)}[/dim]")
        except RuntimeError as e:
            console.print(f"[yellow]跳过 LLM 描述（{e}）[/yellow]")
    text = render_dictionary_markdown(entries, lang)
    for w in warnings:
        console.print(f"[yellow]⚠ {w}[/yellow]")
    if output:
        Path(output).write_text(text, encoding="utf-8")
        console.print(f"[green]数据字典已写入 {output}[/green]"
                      f"（{len(entries)} 表）")
    else:
        console.print(text, markup=False)


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


@cli.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--sql", "-s", type=str, default=None, help="SQL text to analyze")
@click.option("--file", "-f", "sql_file", type=click.Path(exists=True), default=None,
              help="SQL file to analyze")
@click.option("--dir", "-D", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="Analyze every *.sql file under a directory (recursive)")
@click.option("--dialect", "-d", type=click.Choice(["spark", "maxcompute", "hive"]),
              default="spark", show_default=True, help="SQL dialect")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--llm", "use_llm", is_flag=True,
              help="Also rewrite the SQL with the LLM (needs API key; default is static-only)")
@click.option("--fail-on", type=click.Choice(["high", "medium", "low"]), default=None,
              help="Exit 1 when findings at/above this severity exist (CI gate)")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def skew(
    paths: tuple[str, ...],
    sql: str | None,
    sql_file: str | None,
    directory: str | None,
    dialect: str,
    lang: str,
    use_llm: bool,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """SQL 数据倾斜分析 — static skew-pattern scan, optional LLM rewrite.

    PATHS: optional *.sql files or directories (as passed by pre-commit)."""
    import json as _json
    from pathlib import Path

    from .data_skew.history import default_history
    from .data_skew.report import Severity, render_report
    from .sql_review.runner import collect_sql_files

    # ── collect analysis targets ──
    sources: list[tuple[str, str]] = []
    try:
        if sql:
            sources.append(("<inline>", sql))
        if sql_file:
            sources.append((sql_file, Path(sql_file).read_text(encoding="utf-8")))
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
    except (OSError, UnicodeDecodeError) as e:
        console.print(f"[red]收集分析目标失败:[/red] {e}")
        sys.exit(1)
    seen: set[str] = set()
    sources = [(label, text) for label, text in sources
               if not (label in seen or seen.add(label))]
    if not sources:
        raise click.UsageError("Provide SQL via --sql / --file / --dir or positional paths")

    # ── analyze ──
    history = default_history()
    results = []  # (label, SkewReport, markdown)
    for label, text in sources:
        if use_llm:
            from .config import load_settings
            from .data_skew.agent import DataSkewAgent
            try:
                settings = load_settings()
            except RuntimeError as e:
                raise click.ClickException(f"--llm 需要 LLM 配置: {e}")
            agent = DataSkewAgent(settings, dialect=dialect, lang=lang)
            res = agent.analyze(text, use_llm=True)
            rep, md = res.report, res.markdown
        else:
            from .data_skew.agent import static_skew_report
            rep = static_skew_report(text, dialect, lang)
            md = render_report(rep, lang)
        history.log(text, rep, mode="llm" if use_llm else "static", source="cli")
        results.append((label, rep, md))

    # ── render ──
    if fmt == "json":
        payload = [
            {
                "file": label,
                "dialect": rep.dialect,
                "counts": {"high": len(rep.high), "medium": len(rep.medium),
                           "low": len(rep.low)},
                "findings": [f.to_dict() for f in rep.findings],
            }
            for label, rep, _ in results
        ]
        text_out = _json.dumps(payload, ensure_ascii=False, indent=2)
        print(text_out)
    else:
        parts = []
        for label, _, md in results:
            head = f"# 📄 {label}\n\n" if len(results) > 1 else ""
            parts.append(head + md)
        text_out = "\n\n---\n\n".join(parts)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    # ── CI gate ──
    if fail_on:
        rank = {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}
        threshold = {"low": 1, "medium": 2, "high": 3}[fail_on]
        worst = max((rank[f.severity] for _, rep, _ in results
                     for f in rep.findings), default=0)
        if worst >= threshold:
            msg = f"存在 {fail_on} 及以上级别的倾斜风险，检查未通过。"
            if fmt == "json":
                # keep stdout valid JSON for `... -F json | jq` pipelines
                print(msg, file=sys.stderr)
            else:
                console.print(f"\n[red]{msg}[/red]")
            sys.exit(1)


@cli.command(name="skew-stats")
@click.option("--recent", "-n", type=int, default=20, help="显示最近 N 条")
def skew_stats(recent: int) -> None:
    """数据倾斜分析历史与统计 (logs/data_skew.jsonl)。"""
    from collections import Counter

    from .data_skew.history import default_history

    records = default_history().recent(recent)
    if not records:
        console.print("[yellow]还没有数据倾斜分析记录。[/yellow]")
        return
    console.print("[bold]数据倾斜分析历史[/bold]")
    marks = {"high": "⛔", "medium": "⚠️", "clean": "✅"}
    for r in records:
        c = r.get("counts") or {}
        snippet = " ".join((r.get("sql") or "").split())[:60]
        console.print(
            f"  {r.get('timestamp', '')}  [{r.get('mode', '')}/{r.get('source', '')}] "
            f"{r.get('dialect', '')}  "
            f"⛔{c.get('high', 0)} ⚠️{c.get('medium', 0)} 🔵{c.get('low', 0)}  "
            f"{marks.get(r.get('verdict', ''), '')}  {snippet}")
    verdicts = Counter(r.get("verdict", "clean") for r in records)
    sources = Counter(r.get("source", "?") for r in records)
    dialects = Counter(r.get("dialect", "?") for r in records)
    console.print(
        f"\n[bold]汇总[/bold] 共 {len(records)} 次 · "
        f"高风险 {verdicts.get('high', 0)} 次 · "
        f"潜在 {verdicts.get('medium', 0)} 次 · 干净 {verdicts.get('clean', 0)} 次")
    console.print(
        "[bold]来源[/bold] " + " · ".join(f"{k}×{v}" for k, v in sources.most_common())
        + "   [bold]方言[/bold] "
        + " · ".join(f"{k}×{v}" for k, v in dialects.most_common()))
    llm_runs = sum(1 for r in records if r.get("mode") == "llm")
    optimized = sum(1 for r in records if r.get("optimized"))
    if llm_runs:
        console.print(f"[bold]LLM 改写[/bold] {llm_runs} 次,产出优化 SQL {optimized} 次")


@cli.command(name="skew-mcp")
@click.option("--dialect", "-d", type=click.Choice(["spark", "maxcompute", "hive"]),
              default="spark", show_default=True, help="Default SQL dialect")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Default report language")
def skew_mcp(dialect: str, lang: str) -> None:
    """以 MCP server（stdio）暴露数据倾斜静态分析，供 Claude Desktop 等 MCP 客户端调用。"""
    from .data_skew.mcp_server import create_mcp_server

    try:
        server = create_mcp_server(default_dialect=dialect, default_lang=lang)
    except RuntimeError as exc:
        raise click.ClickException(str(exc))
    server.run()


@cli.command(name="t2s-bench")
@click.option("--ddl", type=click.Path(exists=True), required=True,
              help="schema DDL 文件（表白名单）")
@click.option("--bench", "-b", "bench_file", type=click.Path(exists=True), required=True,
              help="评测集 JSONL（{question, tables} 每行一条）")
@click.option("--mode", type=click.Choice(["keyword", "hybrid", "both"]),
              default="both", show_default=True, help="评测模式")
@click.option("--gate", is_flag=True,
              help="回归门禁：hybrid Top3 低于 keyword 时退出码 1")
def t2s_bench(ddl: str, bench_file: str, mode: str, gate: bool) -> None:
    """Text2SQL 表检索评测：对比 keyword-only 与 hybrid 的 Top1/Top3 命中率。"""
    _ensure_utf8_stdio()
    from .text2sql.bench import load_bench, render_bench_report, run_bench
    from .text2sql.schema import SchemaStore

    store = SchemaStore.from_file(ddl)
    try:
        cases = load_bench(bench_file)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    if not cases:
        raise click.ClickException("评测集为空")

    modes = ["keyword", "hybrid"] if mode == "both" else [mode]
    results = [run_bench(store, cases, m) for m in modes]
    console.print(render_bench_report(results))

    if gate and len(results) == 2:
        kw, hy = results[0], results[1]
        if hy.top3 < kw.top3:
            console.print(
                f"[red]回归门禁失败: hybrid Top3 {hy.top3_rate:.1%} < "
                f"keyword {kw.top3_rate:.1%}[/red]"
            )
            raise SystemExit(1)
        console.print("[green]回归门禁通过: hybrid 不低于 keyword[/green]")


@cli.command(name="t2s-index-values")
@click.option("--ddl", type=click.Path(exists=True), default=None,
              help="schema DDL 文件（默认 SCHEMA_DDL_PATH / config/schema_ddl.sql）")
@click.option("--ds-type", type=str, default="sqlite", show_default=True,
              help="数据源类型")
@click.option("--database", type=str, default="",
              help="sqlite 数据库文件路径（仅 --ds-type sqlite 需要）")
@click.option("--connection", type=str, default="",
              help="已保存连接的名称（settings 页配置），优先于环境变量")
def t2s_index_values(ddl: str | None, ds_type: str, database: str,
                     connection: str) -> None:
    """构建值级检索索引：采样低基数字符串列的枚举值（问题里的取值 → 表/列/字面量）。"""
    _ensure_utf8_stdio()
    import os as _os

    from .text2sql.executor import create_executor
    from .text2sql.retrieval import schema_hash
    from .text2sql.schema import SchemaStore
    from .text2sql.subscriptions import resolve_db_config
    from .text2sql.values import ValueIndex

    from pathlib import Path

    ddl_path = ddl or _os.getenv("SCHEMA_DDL_PATH", "config/schema_ddl.sql")
    if not Path(ddl_path).is_file():
        raise click.ClickException(f"DDL 文件不存在: {ddl_path}")
    store = SchemaStore.from_file(ddl_path)
    db_config = resolve_db_config({
        "ds_type": ds_type, "connection": connection, "database": database,
    })
    if db_config is None:
        raise click.ClickException("无法解析数据库连接（连接名/环境变量）")
    executor = create_executor(db_config)
    index = ValueIndex.build(executor, store)
    if len(index) == 0:
        console.print("[yellow]未采样到任何值（分区表被跳过；检查列类型/数据）[/yellow]")
        return
    path = index.save(schema_hash(store))
    n_tables = len(index.data)
    console.print(
        f"[green]值索引已构建: {n_tables} 张表 / {len(index)} 列 -> {path}[/green]"
    )


@cli.command(name="t2s-search")
@click.argument("query")
@click.option("--ddl", type=click.Path(exists=True), default=None,
              help="schema DDL 文件（默认 SCHEMA_DDL_PATH / config/schema_ddl.sql）")
@click.option("--metrics", "metrics_file", type=click.Path(exists=True), default=None,
              help="指标定义文件（默认 config/metrics.yaml）")
@click.option("--top", "-n", type=int, default=5, show_default=True, help="每类返回条数")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="输出格式")
def t2s_search(query: str, ddl: str | None, metrics_file: str | None,
               top: int, fmt: str) -> None:
    """数据目录检索：一句话同时搜表/指标/取值（复用混合检索与值索引，免 LLM）。"""
    _ensure_utf8_stdio()
    import json as _json
    import os as _os
    from pathlib import Path

    from .text2sql.catalog import render_catalog_markdown, search_catalog
    from .text2sql.metrics import load_metric_store
    from .text2sql.retrieval import schema_hash
    from .text2sql.schema import SchemaStore
    from .text2sql.values import ValueIndex

    ddl_path = ddl or _os.getenv("SCHEMA_DDL_PATH", "config/schema_ddl.sql")
    if not Path(ddl_path).is_file():
        raise click.ClickException(f"DDL 文件不存在: {ddl_path}")
    store = SchemaStore.from_file(ddl_path)
    metric_store, errors = load_metric_store(store, path=metrics_file)
    for e in errors[:3]:
        console.print(f"[yellow]指标定义警告: {e}[/yellow]")
    value_index = ValueIndex.load(schema_hash(store))  # None when not built

    result = search_catalog(
        query, store, metric_store=metric_store,
        value_index=value_index, top_n=top,
    )
    if fmt == "json":
        console.print(_json.dumps(result, ensure_ascii=False, indent=2))
    else:
        console.print(render_catalog_markdown(result))


@cli.command(name="t2s-mcp")
@click.option("--ddl", type=click.Path(exists=True), default=None,
              help="schema DDL 文件（默认 SCHEMA_DDL_PATH / config/schema_ddl.sql）")
@click.option("--metrics", "metrics_file", type=click.Path(exists=True), default=None,
              help="指标定义文件（默认 config/metrics.yaml）")
@click.option("--ds-type", type=str, default="hive", show_default=True,
              help="SQL 方言 / 数据源类型")
@click.option("--allow-execute", is_flag=True,
              help="开放 execute_readonly_sql 工具（默认只出 SQL 不执行）")
@click.option("--database", type=str, default="",
              help="sqlite 数据库文件路径（仅 --ds-type sqlite 需要）")
def t2s_mcp(ddl: str | None, metrics_file: str | None, ds_type: str,
            allow_execute: bool, database: str) -> None:
    """以 MCP server（stdio）暴露 Chat BI 确定性能力：表检索、指标口径、指标 SQL 展开。"""
    from .text2sql.mcp_server import create_mcp_server

    try:
        server = create_mcp_server(
            ddl_path=ddl or "", metrics_path=metrics_file or "",
            ds_type=ds_type, allow_execute=allow_execute, database=database,
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc))
    server.run()


@cli.command()
@click.option("--dir", "-d", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="SQL 目录（递归扫描 *.sql）")
@click.option("--sql", type=str, default=None, help="直接扫描一段 SQL")
@click.option("--file", "-f", "sql_file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="扫描单个 SQL 文件")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/...)")
@click.option("--rules", "rules_path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="自定义规则 YAML（追加到内置规则）")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["high", "medium", "low"]),
              default=None, help="CI gate: exit 1 when findings at/above this level exist")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def pii(
    directory: str | None,
    sql: str | None,
    sql_file: str | None,
    dialect: str,
    rules_path: str | None,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """敏感数据扫描 — 命名规则 × 字段血缘，静态识别 PII 列及未脱敏扩散。"""
    import json as _json
    from pathlib import Path

    from .pii_scan import (
        DEFAULT_RULES, load_extra_rules, render_markdown, report_to_dict,
        scan_dir, scan_files, scan_sql_text,
    )

    if not directory and not sql and not sql_file:
        raise click.UsageError("Provide --dir / --sql / --file")

    rules = list(DEFAULT_RULES)
    if rules_path:
        try:
            rules += load_extra_rules(rules_path)
        except ValueError as exc:
            raise click.ClickException(str(exc))

    try:
        if directory:
            report = scan_dir(directory, dialect=dialect, rules=rules)
        elif sql_file:
            report = scan_files([Path(sql_file)], dialect=dialect,
                                rules=rules, root=sql_file)
        else:
            report = scan_sql_text(sql, dialect=dialect, rules=rules)
    except (OSError, UnicodeDecodeError) as exc:
        console.print(f"[red]扫描失败:[/red] {exc}")
        sys.exit(1)

    if fmt == "json":
        text_out = _json.dumps(report_to_dict(report, lang),
                               ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_markdown(report, lang)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    if fail_on:
        rank = {"low": 1, "medium": 2, "high": 3}
        threshold = rank[fail_on]
        worst = max((rank[f.severity] for f in report.findings), default=0)
        if worst >= threshold:
            msg = f"存在 {fail_on} 及以上级别的敏感列风险，检查未通过。"
            if fmt == "json":
                print(msg, file=sys.stderr)
            else:
                console.print(f"\n[red]{msg}[/red]")
            sys.exit(1)


@cli.command()
@click.option("--dir", "-d", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="日志目录（递归扫描）")
@click.option("--file", "-f", "log_file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="巡检单个日志文件")
@click.option("--pattern", "-p", "patterns", multiple=True,
              help="文件通配符，可多次指定（默认 *.log / *.log.* / *.out / *.err）")
@click.option("--no-warn", is_flag=True, help="只聚类 ERROR/FATAL，忽略 WARN")
@click.option("--top", "-n", type=int, default=10, show_default=True,
              help="报告中展示的 Top 簇数")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["error", "warn"]),
              default=None, help="CI gate: exit 1 when clusters at/above this level exist")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def loginspect(
    directory: str | None,
    log_file: str | None,
    patterns: tuple[str, ...],
    no_warn: bool,
    top: int,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """批量日志巡检 — 对日志目录做异常聚类，收敛成 Top-N 个根因。"""
    import json as _json
    from pathlib import Path

    from .log_inspect import (
        render_markdown, report_to_dict, scan_dir, scan_files,
    )
    from .log_inspect.clusterer import DEFAULT_PATTERNS

    if not directory and not log_file:
        raise click.UsageError("Provide --dir or --file")

    include_warn = not no_warn
    if directory:
        report = scan_dir(directory,
                          patterns=tuple(patterns) or DEFAULT_PATTERNS,
                          include_warn=include_warn)
    else:
        report = scan_files([Path(log_file)], include_warn=include_warn,
                            root=log_file)

    if fmt == "json":
        text_out = _json.dumps(report_to_dict(report, top=top),
                               ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_markdown(report, lang, top=top)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    if fail_on:
        c = report.counts()
        hit = c["error"] > 0 or (fail_on == "warn" and c["warn"] > 0)
        if hit:
            msg = f"存在 {fail_on} 及以上级别的日志异常簇，检查未通过。"
            if fmt == "json":
                print(msg, file=sys.stderr)
            else:
                console.print(f"\n[red]{msg}[/red]")
            sys.exit(1)


@cli.command(name="schemadiff")
@click.option("--old", "old_path", type=click.Path(exists=True), required=True,
              help="旧版 DDL：文件或目录（递归 *.sql）")
@click.option("--new", "new_path", type=click.Path(exists=True), required=True,
              help="新版 DDL：文件或目录（递归 *.sql）")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/...)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["breaking", "risk", "info"]),
              default=None, help="CI gate: exit 1 when findings at/above this level exist")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
@click.option("--emit-ddl", "emit_ddl", type=click.Path(), default=None,
              help="生成迁移 ALTER 脚本到该路径（破坏性变更只注释,不自动执行）")
def schemadiff(
    old_path: str,
    new_path: str,
    dialect: str,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
    emit_ddl: str | None,
) -> None:
    """Schema 漂移检查 — 对比两份 DDL 快照，按破坏/风险/提示分级报告变更。"""
    import json as _json
    from pathlib import Path

    from .schema_drift import diff_paths, render_markdown, report_to_dict

    report = diff_paths(old_path, new_path, dialect=dialect)

    if fmt == "json":
        text_out = _json.dumps(report_to_dict(report, lang),
                               ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_markdown(report, lang)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    if emit_ddl:
        from .schema_drift import generate_migration, load_schemas, render_migration_sql

        new_schemas, _ = load_schemas(new_path, dialect=dialect)
        plan = generate_migration(report, new_schemas)
        Path(emit_ddl).write_text(render_migration_sql(plan), encoding="utf-8")
        console.print(
            f"[green]迁移脚本已生成: {emit_ddl} "
            f"(自动 {plan.auto_count} 条 / 人工确认 {plan.manual_count} 条)[/green]"
        )

    if fail_on:
        rank = {"info": 1, "risk": 2, "breaking": 3}
        threshold = rank[fail_on]
        worst = max((rank[f.severity] for f in report.findings), default=0)
        if worst >= threshold:
            msg = f"存在 {fail_on} 及以上级别的 Schema 变更，检查未通过。"
            if fmt == "json":
                print(msg, file=sys.stderr)
            else:
                console.print(f"\n[red]{msg}[/red]")
            sys.exit(1)


@cli.command()
@click.option("--sql", type=str, default=None, help="需要造数的查询 SQL")
@click.option("--file", "-f", "sql_file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="从文件读取查询 SQL")
@click.option("--ddl", "ddl_file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="CREATE TABLE 脚本（提供精确列类型）")
@click.option("--rows", "-n", type=click.IntRange(1, 100), default=5,
              show_default=True, help="每表生成行数")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/...)")
@click.option("--out", "out_dir", type=click.Path(file_okay=False), default=None,
              help="写出 CSV + create_tables.sql + inserts.sql 的目录")
@click.option("--validate/--no-validate", "do_validate", default=True,
              show_default=True, help="在内存 SQLite 上执行数据+查询验证")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["error"]), default=None,
              help="CI gate: exit 1 when parsing fails or SQLite validation errors")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def testgen(
    sql: str | None,
    sql_file: str | None,
    ddl_file: str | None,
    rows: int,
    dialect: str,
    out_dir: str | None,
    do_validate: bool,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """SQL 测试数据生成 — 关联感知造数 + 可选 SQLite 链路验证。"""
    import json as _json
    from pathlib import Path

    from .sql_testgen import (
        generate, render_markdown, result_to_dict, validate_with_sqlite,
        write_outputs,
    )

    if not sql and not sql_file:
        raise click.UsageError("Provide --sql or --file")
    if sql_file:
        sql = Path(sql_file).read_text(encoding="utf-8")
    ddl = Path(ddl_file).read_text(encoding="utf-8") if ddl_file else ""

    result = generate(sql, ddl=ddl, rows=rows, dialect=dialect)
    if do_validate and result.tables:
        result.validation = validate_with_sqlite(result)

    if fmt == "json":
        text_out = _json.dumps(result_to_dict(result),
                               ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_markdown(result, lang)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")
    if out_dir and result.tables:
        written = write_outputs(result, out_dir)
        console.print(f"[dim]已写出 {len(written)} 个文件到 {out_dir}[/dim]")

    if fail_on == "error":
        failed = bool(result.warnings) or (
            result.validation is not None
            and result.validation.status in ("transpile_error", "exec_error"))
        if failed:
            msg = "测试数据生成或验证失败，检查未通过。"
            if fmt == "json":
                print(msg, file=sys.stderr)
            else:
                console.print(f"\n[red]{msg}[/red]")
            sys.exit(1)


@cli.command(name="mcp")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Default report language")
@click.option("--sql-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="启用血缘工具：从目录下的 *.sql 构建血缘图（递归）")
@click.option("--sql-dialect", type=click.Choice(
                  ["hive", "spark", "flink", "maxcompute", "mysql",
                   "postgresql", "clickhouse", "doris", "starrocks", "sqlite"]),
              default="hive", show_default=True,
              help="解析 --sql-dir 脚本用的 SQL 方言")
@click.option("--seatunnel-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="启用血缘工具：从 SeaTunnel 配置目录构建 source→sink 血缘")
@click.option("--hive", "use_hive", is_flag=True,
              help="启用血缘工具：从 Hive 元数据血缘表构建（需 .env 配置）")
@click.option("--meta-table", type=str, default=None,
              help="血缘元数据表名（默认 zz.dwm_meta_table_lineage_df）")
@click.option("--partition", type=str, default=None,
              help="指定 pt 分区（默认自动取最新分区）")
@click.option("--connections", type=str, default=None,
              help="数据库工具可用的连接名白名单（逗号分隔；默认全部已保存连接）")
@click.option("--no-db", "no_db", is_flag=True,
              help="纯静态模式：只暴露 6 个静态分析工具，不加载任何数据库工具")
def mcp_toolbox_cmd(
    lang: str,
    sql_dir: str | None,
    sql_dialect: str,
    seatunnel_dir: str | None,
    use_hive: bool,
    meta_table: str | None,
    partition: str | None,
    connections: str | None,
    no_db: bool,
) -> None:
    """统一 MCP 工具箱（stdio）：SQL 审查/方言翻译/倾斜分析/变更影响/配置迁移
    + 已保存连接上的表结构浏览、只读查询与跨库比对。全部确定性实现，不调用
    LLM。血缘工具在给出 --sql-dir / --seatunnel-dir / --hive 之一时加载。"""
    from .mcp_toolbox import create_mcp_server

    allow = ([n.strip() for n in connections.split(",") if n.strip()]
             if connections else None)
    try:
        server = create_mcp_server(
            default_lang=lang, sql_dir=sql_dir, seatunnel_dir=seatunnel_dir,
            use_hive=use_hive, meta_table=meta_table, partition=partition,
            sql_dialect=sql_dialect, connections=allow, include_db=not no_db,
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc))
    server.run()


@cli.group(name="t2s-sub")
def t2s_sub() -> None:
    """Chat BI 订阅：定时执行指标/收藏查询并推送飞书卡片。"""


@t2s_sub.command("list")
def t2s_sub_list() -> None:
    """列出全部订阅及其上次执行状态。"""
    _ensure_utf8_stdio()
    from .text2sql.subscriptions import SubscriptionStore

    subs = SubscriptionStore().list()
    if not subs:
        console.print("暂无订阅（用 t2s-sub add 创建）")
        return
    from rich.table import Table
    table = Table(title=f"订阅（{len(subs)} 个）")
    for col in ("id", "名称", "cron", "来源", "启用", "上次执行", "状态"):
        table.add_column(col)
    for s in subs:
        source = (s.get("metric") if s.get("source_type") == "metric"
                  else f"fav:{s.get('favorite_id')}")
        table.add_row(
            s.get("id", ""), s.get("name", ""), s.get("cron", ""),
            source or "", "✓" if s.get("enabled", True) else "✗",
            s.get("last_run_at", "") or "-", s.get("last_status", "") or "-",
        )
    console.print(table)


@t2s_sub.command("add")
@click.option("--name", required=True, help="订阅名称")
@click.option("--cron", "cron_expr", required=True,
              help="5 字段 cron：分 时 日 月 周（周 0=周一）")
@click.option("--metric", default="", help="指标名（与 --favorite 二选一）")
@click.option("--favorite", "favorite_id", default="", help="收藏查询 ID")
@click.option("--dim", "-d", "dims", multiple=True, help="下钻维度（可多次，仅指标订阅）")
@click.option("--lookback", type=int, default=1, show_default=True,
              help="回看天数：查询 [今天-N, 昨天]（仅指标订阅）")
@click.option("--param", "-p", "params", multiple=True,
              help="收藏参数 key=value（可多次；内置宏 today/yesterday/*_pt 自动生效）")
@click.option("--ds-type", default="hive", show_default=True)
@click.option("--connection", default="", help="连接预设名（设置页保存的连接）")
@click.option("--database", default="", help="sqlite 数据库路径（仅 sqlite）")
@click.option("--webhook", default="", help="飞书 incoming webhook URL")
@click.option("--watch", is_flag=True,
              help="异动监控订阅：昨天 vs 参照期,变动超阈值才推送告警")
@click.option("--threshold", type=float, default=10.0, show_default=True,
              help="异动阈值百分比（仅 --watch）")
@click.option("--watch-mode", type=click.Choice(["dod", "wow"]), default="dod",
              show_default=True, help="参照期：dod=前一天, wow=上周同日（仅 --watch）")
@click.option("--table", default="",
              help="SLA 分区监控的表名（与 --metric/--favorite 互斥）")
@click.option("--lag", "lag_days", type=int, default=1, show_default=True,
              help="SLA 容忍滞后天数：最新分区最迟 T-N（仅 --table）")
def t2s_sub_add(name: str, cron_expr: str, metric: str, favorite_id: str,
                dims: tuple[str, ...], lookback: int, params: tuple[str, ...],
                ds_type: str, connection: str, database: str, webhook: str,
                watch: bool, threshold: float, watch_mode: str,
                table: str, lag_days: int) -> None:
    """新建订阅（--metric 推数 / --metric --watch 异动告警 / --favorite 收藏推数 / --table 分区SLA告警）。"""
    _ensure_utf8_stdio()
    from .text2sql.subscriptions import SubscriptionStore

    if sum(map(bool, (metric, favorite_id, table))) != 1:
        raise click.UsageError("--metric / --favorite / --table 必须三选一")
    if watch and not metric:
        raise click.UsageError("--watch 只能与 --metric 搭配")
    param_map: dict[str, str] = {}
    for p in params:
        if "=" not in p:
            raise click.UsageError(f"--param 格式应为 key=value: {p}")
        k, v = p.split("=", 1)
        param_map[k.strip()] = v
    if table:
        source_type = "partition_watch"
    elif watch:
        source_type = "metric_watch"
    else:
        source_type = "metric" if metric else "favorite"
    try:
        entry = SubscriptionStore().add(
            name=name, cron=cron_expr,
            source_type=source_type,
            metric=metric, dimensions=list(dims), lookback_days=lookback,
            favorite_id=favorite_id, params=param_map,
            threshold_pct=threshold, watch_mode=watch_mode,
            ds_type=ds_type, connection=connection, database=database,
            webhook_url=webhook, table=table, lag_days=lag_days,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))
    console.print(f"[green]已创建订阅 {entry['id']}: {entry['name']}[/green]")


@t2s_sub.command("rm")
@click.argument("sub_id")
def t2s_sub_rm(sub_id: str) -> None:
    """删除订阅。"""
    from .text2sql.subscriptions import SubscriptionStore

    if not SubscriptionStore().delete(sub_id):
        raise click.ClickException(f"订阅 '{sub_id}' 不存在")
    console.print("[green]已删除[/green]")


@t2s_sub.command("enable")
@click.argument("sub_id")
@click.option("--off", is_flag=True, help="停用而非启用")
def t2s_sub_enable(sub_id: str, off: bool) -> None:
    """启用/停用订阅。"""
    from .text2sql.subscriptions import SubscriptionStore

    if not SubscriptionStore().set_enabled(sub_id, not off):
        raise click.ClickException(f"订阅 '{sub_id}' 不存在")
    console.print(f"[green]已{'停用' if off else '启用'}[/green]")


@t2s_sub.command("run")
@click.argument("sub_id")
def t2s_sub_run(sub_id: str) -> None:
    """立即执行一次订阅（不等 cron）。"""
    _ensure_utf8_stdio()
    from .text2sql.subscriptions import SubscriptionStore, run_subscription

    store = SubscriptionStore()
    sub = store.get(sub_id)
    if sub is None:
        raise click.ClickException(f"订阅 '{sub_id}' 不存在")
    outcome = run_subscription(sub)
    store.record_run(sub_id, outcome.get("status", "error"), outcome.get("error", ""))
    if outcome["status"] == "success":
        console.print(f"[green]执行成功: {outcome['row_count']} 行[/green]")
        console.print(outcome["sql"])
    else:
        console.print(f"[red]执行失败: {outcome.get('error', '')}[/red]")
        raise SystemExit(1)


@cli.command(name="t2s-cron")
@click.option("--once", is_flag=True, help="只检查一次到期订阅后退出（供外部调度器调用）")
@click.option("--tick", type=int, default=20, show_default=True, help="轮询间隔秒")
def t2s_cron(once: bool, tick: int) -> None:
    """订阅调度器：常驻轮询 cron 到期的订阅并执行（无 UI 部署用）。"""
    _ensure_utf8_stdio()
    import time as _time

    from .text2sql.subscriptions import Scheduler

    scheduler = Scheduler(tick_seconds=tick)
    if once:
        fired = scheduler.check_once()
        console.print(f"到期执行 {len(fired)} 个订阅" + (f": {', '.join(fired)}" if fired else ""))
        return
    console.print(f"订阅调度器已启动（每 {tick}s 检查一次，Ctrl+C 退出）")
    scheduler.start()
    try:
        while True:
            _time.sleep(3600)
    except KeyboardInterrupt:
        scheduler.stop()
        console.print("已退出")


@cli.command(name="t2s-eval")
@click.option("--dataset", type=click.Path(exists=True), required=True,
              help="评测集 JSONL（{question, golden_sql} 每行一条）")
@click.option("--ddl", type=click.Path(exists=True), default=None,
              help="schema DDL（sqlite 缺省时自动内省）")
@click.option("--ds-type", default="sqlite", show_default=True)
@click.option("--database", default="", help="sqlite 数据库路径")
@click.option("--connection", default="", help="连接预设名（设置页保存的连接）")
@click.option("--limit", type=int, default=0, help="只评前 N 题（控成本试跑）")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="报告写入文件")
@click.pass_context
def t2s_eval(ctx: click.Context, dataset: str, ddl: str | None, ds_type: str,
             database: str, connection: str, limit: int,
             output: str | None) -> None:
    """Text2SQL 端到端评测：问题→agent(真实 LLM)→结果集 与 golden SQL 对比。

    换 --model/--provider 重跑即可做多模型准确率对比。
    """
    _ensure_utf8_stdio()
    from .text2sql.evaluate import (
        load_dataset,
        make_agent_runner,
        render_eval_report,
        run_eval,
    )
    from .text2sql.metrics import load_metric_store
    from .text2sql.schema import SchemaStore
    from .text2sql.subscriptions import resolve_db_config

    try:
        settings = _settings_with_overrides(ctx)
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    try:
        cases = load_dataset(dataset)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    if limit > 0:
        cases = cases[:limit]
    if not cases:
        raise click.ClickException("评测集为空")

    db_config = resolve_db_config({
        "ds_type": ds_type, "connection": connection, "database": database,
    })
    if db_config is None:
        raise click.ClickException("无法解析数据库连接")

    if ddl:
        store = SchemaStore.from_file(ddl)
    else:
        from .text2sql.executor import create_executor
        store = SchemaStore.from_db(create_executor(db_config))
    if len(store) == 0:
        raise click.ClickException("未加载到任何表")
    metric_store, _errs = load_metric_store(store)

    runner = make_agent_runner(
        settings, store, ds_type, db_config,
        metric_store=metric_store if len(metric_store) else None,
    )
    console.print(f"共 {len(cases)} 题,模型 {settings.model_name},开始评测...")
    report = run_eval(cases, runner, db_config, store=store)
    text = render_eval_report(report, model_name=settings.model_name)
    console.print(text)
    if output:
        from pathlib import Path as _P
        _P(output).write_text(text, encoding="utf-8")
        console.print(f"[green]报告已写入 {output}[/green]")


def _settings_with_overrides(ctx: click.Context):
    """load_settings honoring the global --model/--provider overrides."""
    model = (ctx.obj or {}).get("model") if ctx.obj else None
    provider = (ctx.obj or {}).get("provider") if ctx.obj else None
    old_model = os.environ.get("MODEL_NAME")
    old_provider = os.environ.get("LLM_PROVIDER")
    try:
        if model:
            os.environ["MODEL_NAME"] = model
        if provider:
            os.environ["LLM_PROVIDER"] = provider
        from .config import load_settings
        return load_settings()
    finally:
        for key, old in (("MODEL_NAME", old_model), ("LLM_PROVIDER", old_provider)):
            if os.environ.get(key) != (old or ""):
                if old is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old


@cli.group()
def dqc() -> None:
    """DQC 数据质量：规则化表级检查（行数/空值率/唯一性/枚举域）。"""


@dqc.command("validate")
@click.option("--rules", "-r", "rules_file", type=click.Path(exists=True),
              required=True, help="DQC 规则 YAML")
@click.option("--ddl", type=click.Path(exists=True), required=True,
              help="schema DDL（表白名单），交叉校验表/列存在性")
def dqc_validate(rules_file: str, ddl: str) -> None:
    """校验规则与 DDL 的一致性（CI 门禁：有错误时退出码 1）。"""
    _ensure_utf8_stdio()
    from .data_quality import load_rules, validate_rules
    from .text2sql.schema import SchemaStore

    rules, errors = load_rules(rules_file)
    errors += validate_rules(rules, SchemaStore.from_file(ddl))
    if errors:
        for err in errors:
            console.print(f"[red]{err}[/red]")
        raise SystemExit(1)
    n_checks = sum(len(r.checks) for r in rules)
    console.print(f"[green]校验通过：{len(rules)} 张表 / {n_checks} 项检查[/green]")


@dqc.command("run")
@click.option("--rules", "-r", "rules_file", type=click.Path(exists=True),
              required=True, help="DQC 规则 YAML")
@click.option("--ddl", type=click.Path(exists=True), default=None,
              help="schema DDL（给出时检查 SQL 也过白名单校验）")
@click.option("--ds-type", default="hive", show_default=True)
@click.option("--database", default="", help="sqlite 数据库路径（仅 sqlite）")
@click.option("--connection", default="", help="连接预设名（设置页保存的连接）")
@click.option("--webhook", default="", help="有不通过项时推送飞书告警卡片")
@click.option("--fail-on-violation/--no-fail-on-violation", default=True,
              show_default=True, help="有不通过/异常项时退出码 1（CI 门禁）")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="报告写入文件")
def dqc_run(rules_file: str, ddl: str | None, ds_type: str, database: str,
            connection: str, webhook: str, fail_on_violation: bool,
            output: str | None) -> None:
    """执行全部质量检查并输出报告。"""
    _ensure_utf8_stdio()
    from .data_quality import load_rules, render_report, run_checks
    from .data_quality.runner import push_failures
    from .text2sql.executor import create_executor
    from .text2sql.subscriptions import resolve_db_config

    rules, errors = load_rules(rules_file)
    if errors:
        for err in errors:
            console.print(f"[red]{err}[/red]")
        raise SystemExit(1)
    if not rules:
        raise click.ClickException("规则文件为空")

    schema_store = None
    if ddl:
        from .text2sql.schema import SchemaStore
        schema_store = SchemaStore.from_file(ddl)

    db_config = resolve_db_config({
        "ds_type": ds_type, "connection": connection, "database": database,
    })
    if db_config is None:
        raise click.ClickException(
            "无法解析数据库连接（--connection 预设名、--database 或环境变量）")

    results = run_checks(rules, create_executor(db_config),
                         schema_store=schema_store, ds_type=ds_type)
    report = render_report(results)
    console.print(report)
    if output:
        from pathlib import Path as _P
        _P(output).write_text(report, encoding="utf-8")
        console.print(f"[green]报告已写入 {output}[/green]")
    if webhook:
        ok, msg = push_failures(results, webhook)
        if not ok:
            console.print(f"[yellow]告警推送失败: {msg}[/yellow]")
    bad = sum(1 for r in results if r.status != "pass")
    if bad and fail_on_violation:
        raise SystemExit(1)


@cli.command()
@click.option("--sql-dir", type=click.Path(exists=True, file_okay=False),
              required=True, help="数仓 SQL 目录（构建血缘图）")
@click.option("--qlog", type=click.Path(exists=True), default=None,
              help="查询审计日志（默认 logs/text2sql_queries.jsonl）")
@click.option("--days", type=int, default=30, show_default=True,
              help="审计窗口天数")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="报告写入文件")
def govern(sql_dir: str, qlog: str | None, days: int,
           output: str | None) -> None:
    """数据治理建议：血缘图 × 查询审计 → 下线候选/热表/失败高发（只建议不动手）。"""
    _ensure_utf8_stdio()
    from .data_lineage.governance import (
        analyze_governance,
        load_qlog_records,
        render_governance_markdown,
    )
    from .data_lineage.loaders import build_graph

    graph, warnings = build_graph(sql_dir=sql_dir)
    for w in warnings[:5]:
        console.print(f"[yellow]警告: {w}[/yellow]")
    records = load_qlog_records(qlog, days=days)
    report = analyze_governance(graph, records, days=days)
    text = render_governance_markdown(report)
    console.print(text)
    if output:
        from pathlib import Path as _P
        _P(output).write_text(text, encoding="utf-8")
        console.print(f"[green]报告已写入 {output}[/green]")


def _load_metrics_for_cli(metrics_file: str | None, ddl: str | None):
    """Shared loader for the metrics subcommands: (store, errors)."""
    from .text2sql.metrics import load_metric_store

    schema_store = None
    if ddl:
        from .text2sql.schema import SchemaStore
        schema_store = SchemaStore.from_file(ddl)
    return load_metric_store(schema_store, path=metrics_file)


@cli.group()
def metrics() -> None:
    """指标语义层：查看/校验 metrics.yaml 中的指标口径定义（Chat BI）。"""


@metrics.command("list")
@click.option("--file", "-f", "metrics_file", type=click.Path(exists=True),
              default=None, help="指标定义文件（默认 config/metrics.yaml）")
def metrics_list(metrics_file: str | None) -> None:
    """列出全部已定义指标。"""
    _ensure_utf8_stdio()
    store, errors = _load_metrics_for_cli(metrics_file, None)
    for err in errors:
        console.print(f"[yellow]警告: {err}[/yellow]")
    if len(store) == 0:
        console.print("未找到任何指标定义（config/metrics.yaml）")
        return
    from rich.table import Table
    table = Table(title=f"指标目录（{len(store)} 个）")
    for col in ("name", "展示名", "类型", "口径", "单位", "负责人"):
        table.add_column(col)
    for m in store.metrics:
        caliber = (f"{m.numerator} / {m.denominator}" if m.is_ratio
                   else f"{m.expression} FROM {m.table}")
        table.add_row(m.name, m.display_name, m.metric_type, caliber, m.unit, m.owner)
    console.print(table)


@metrics.command("show")
@click.argument("name")
@click.option("--file", "-f", "metrics_file", type=click.Path(exists=True),
              default=None, help="指标定义文件（默认 config/metrics.yaml）")
def metrics_show(name: str, metrics_file: str | None) -> None:
    """查看单个指标的完整口径定义。"""
    _ensure_utf8_stdio()
    store, errors = _load_metrics_for_cli(metrics_file, None)
    for err in errors:
        console.print(f"[yellow]警告: {err}[/yellow]")
    m = store.get(name)
    if m is None:
        known = ", ".join(x.name for x in store.metrics) or "(无)"
        raise click.ClickException(f"指标 '{name}' 未定义。已知指标: {known}")
    console.print(f"[bold]{m.name}[/bold] ({m.display_name})")
    if m.aliases:
        console.print(f"别名: {', '.join(m.aliases)}")
    if m.description:
        console.print(f"口径: {m.description}")
    if m.is_ratio:
        console.print(f"类型: ratio = {m.numerator} / {m.denominator}")
    else:
        console.print(f"类型: additive = {m.expression} FROM {m.table}")
        console.print(f"时间列: {m.time_column or '(无)'}")
        console.print(f"允许维度: {', '.join(m.dimensions) or '(无)'}")
        for f in m.default_filters:
            console.print(f"恒定过滤: {f}")
    if m.unit:
        console.print(f"单位: {m.unit}")
    if m.owner:
        console.print(f"负责人: {m.owner}")


@metrics.command("validate")
@click.option("--file", "-f", "metrics_file", type=click.Path(exists=True),
              default=None, help="指标定义文件（默认 config/metrics.yaml）")
@click.option("--ddl", type=click.Path(exists=True), required=True,
              help="schema DDL 文件（表白名单），用于交叉校验")
def metrics_validate(metrics_file: str | None, ddl: str) -> None:
    """校验指标定义与 DDL 的一致性（CI 门禁：有错误时退出码 1）。"""
    _ensure_utf8_stdio()
    store, errors = _load_metrics_for_cli(metrics_file, ddl)
    if errors:
        for err in errors:
            console.print(f"[red]{err}[/red]")
        raise SystemExit(1)
    console.print(f"[green]校验通过：{len(store)} 个指标定义与 DDL 一致[/green]")


@metrics.command("sql")
@click.argument("name")
@click.option("--file", "-f", "metrics_file", type=click.Path(exists=True),
              default=None, help="指标定义文件（默认 config/metrics.yaml）")
@click.option("--ddl", type=click.Path(exists=True), required=True,
              help="schema DDL 文件（表白名单）")
@click.option("--dim", "-d", "dims", multiple=True, help="下钻维度（可多次）")
@click.option("--start", default=None, help="开始日期 YYYY-MM-DD / yyyyMMdd")
@click.option("--end", default=None, help="结束日期（含）")
@click.option("--max-partition", default=None, help="无时间范围时的最新分区值")
@click.option("--where", "-w", "filters", multiple=True, help="附加过滤条件（可多次）")
def metrics_sql(
    name: str, metrics_file: str | None, ddl: str, dims: tuple[str, ...],
    start: str | None, end: str | None, max_partition: str | None,
    filters: tuple[str, ...],
) -> None:
    """确定性展开指标 SQL（不执行）——同样的参数永远得到同一条 SQL。"""
    _ensure_utf8_stdio()
    from .text2sql.metrics import MetricError, build_metric_sql, parse_time_range

    store, errors = _load_metrics_for_cli(metrics_file, ddl)
    if errors:
        for err in errors:
            console.print(f"[red]{err}[/red]")
        raise SystemExit(1)
    m = store.get(name)
    if m is None:
        known = ", ".join(x.name for x in store.metrics) or "(无)"
        raise click.ClickException(f"指标 '{name}' 未定义。已知指标: {known}")

    from .text2sql.schema import SchemaStore
    schema_store = SchemaStore.from_file(ddl)
    try:
        sql = build_metric_sql(
            m, store, schema_store,
            dimensions=list(dims),
            time_range=parse_time_range(start or "", end or ""),
            max_partition=max_partition,
            extra_filters=list(filters),
        )
    except MetricError as exc:
        raise click.ClickException(str(exc))
    click.echo(sql)


@cli.group(name="t2s-examples")
def t2s_examples() -> None:
    """Chat BI few-shot 示例库：已验证的 问题→SQL 对（准确率飞轮）。"""


@t2s_examples.command("list")
@click.option("--file", "-f", "examples_file", type=click.Path(),
              default=None, help="示例库文件（默认 config/t2s_examples.json）")
def t2s_examples_list(examples_file: str | None) -> None:
    """列出全部示例。"""
    _ensure_utf8_stdio()
    from .text2sql.examples import ExampleStore

    store = ExampleStore(examples_file)
    items = store.list()
    if not items:
        console.print("示例库为空（UI 里对查询结果点 👍 即可沉淀示例）")
        return
    from rich.table import Table
    table = Table(title=f"few-shot 示例库（{len(items)} 条）")
    for col in ("id", "问题", "来源", "SQL"):
        table.add_column(col)
    for it in items:
        table.add_row(
            it.get("id", ""), it.get("question", "")[:50],
            it.get("source", ""), it.get("sql", "").replace("\n", " ")[:60],
        )
    console.print(table)


@t2s_examples.command("add")
@click.option("--question", "-q", required=True, help="自然语言问题")
@click.option("--sql", "-s", required=True, help="对应的正确 SQL")
@click.option("--file", "-f", "examples_file", type=click.Path(),
              default=None, help="示例库文件（默认 config/t2s_examples.json）")
def t2s_examples_add(question: str, sql: str, examples_file: str | None) -> None:
    """手工添加一条验证示例。"""
    _ensure_utf8_stdio()
    from .text2sql.examples import ExampleStore
    from .text2sql.validator import extract_tables

    store = ExampleStore(examples_file)
    try:
        entry = store.add(question=question, sql=sql,
                          tables=extract_tables(sql), source="manual")
    except ValueError as exc:
        raise click.ClickException(str(exc))
    console.print(f"[green]已添加示例 {entry['id']}（现共 {len(store)} 条）[/green]")


@t2s_examples.command("rm")
@click.argument("example_id")
@click.option("--file", "-f", "examples_file", type=click.Path(),
              default=None, help="示例库文件（默认 config/t2s_examples.json）")
def t2s_examples_rm(example_id: str, examples_file: str | None) -> None:
    """按 id 删除一条示例。"""
    _ensure_utf8_stdio()
    from .text2sql.examples import ExampleStore

    store = ExampleStore(examples_file)
    if store.remove(example_id):
        console.print(f"[green]已删除 {example_id}[/green]")
    else:
        raise click.ClickException(f"示例 '{example_id}' 不存在")


@cli.command(name="mcp-stats")
@click.option("--recent", "-n", type=int, default=20, help="显示最近 N 条")
def mcp_stats(recent: int) -> None:
    """MCP 工具箱调用审计与统计 (logs/mcp_toolbox.jsonl)。"""
    import json as _json
    from collections import Counter, defaultdict

    from .mcp_toolbox import _audit_file

    path = _audit_file()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        console.print("[yellow]还没有 MCP 工具调用记录。[/yellow]")
        return
    records = []
    for line in lines:
        try:
            records.append(_json.loads(line))
        except ValueError:
            continue
    if not records:
        console.print("[yellow]还没有 MCP 工具调用记录。[/yellow]")
        return
    console.print("[bold]最近调用[/bold]")
    for r in records[-recent:]:
        mark = "✅" if r.get("ok") else "⛔"
        console.print(
            f"  {r.get('timestamp', '')}  {mark} {r.get('tool', ''):<24} "
            f"{r.get('elapsed_ms', 0):>6} ms  {str(r.get('args', ''))[:60]}")
    by_tool: dict[str, list] = defaultdict(list)
    for r in records:
        by_tool[r.get("tool", "?")].append(r)
    ok_total = sum(1 for r in records if r.get("ok"))
    console.print(
        f"\n[bold]汇总[/bold] 共 {len(records)} 次调用 · 成功 {ok_total} · "
        f"失败 {len(records) - ok_total}")
    rows = sorted(by_tool.items(), key=lambda kv: -len(kv[1]))
    for tool, rs in rows:
        ok = sum(1 for r in rs if r.get("ok"))
        avg = sum(int(r.get("elapsed_ms", 0)) for r in rs) // max(len(rs), 1)
        console.print(f"  {tool:<26} {len(rs):>4} 次 · 成功率 "
                      f"{100 * ok // max(len(rs), 1):>3}% · 平均 {avg} ms")
    fails = Counter(r.get("tool", "?") for r in records if not r.get("ok"))
    if fails:
        top = " · ".join(f"{t}×{c}" for t, c in fails.most_common(5))
        console.print(f"[bold]失败集中在[/bold] {top}")


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


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def uitest(args: tuple[str, ...]) -> None:
    """UI 测试 Agent（run / list / compare / trend，参数原样转发）。

    Examples: seatunnel-agent uitest run --suite smoke --no-llm
    """
    from .ui_testing.__main__ import main as uitest_main
    sys.exit(uitest_main(list(args) or ["run", "--suite", "smoke"]))


@cli.command()
@click.option("--clear", "clear_", is_flag=True,
              help="清除界面保存的 LLM 配置覆盖（恢复 .env）")
@click.option("--usage", "usage_", is_flag=True,
              help="显示近 30 天 LLM token 用量（按模型汇总；读取当前目录的 "
                   "logs/llm_usage.jsonl，请在项目根目录运行）")
def settings(clear_: bool, usage_: bool) -> None:
    """查看当前生效的 LLM 配置（界面覆盖 or .env），或清除界面覆盖。"""
    from dotenv import load_dotenv

    from . import settings_store

    load_dotenv()
    settings_store.apply_to_env()
    if clear_:
        settings_store.clear()
        console.print("[green]OK[/green] 已清除界面覆盖，恢复 .env 配置")
        return
    if usage_:
        from .llm_usage import format_markdown
        console.print(format_markdown("zh"))
        return
    src = ("界面设置（覆盖 .env） — " + str(settings_store.store_path())
           if settings_store.has_saved() else ".env / 环境变量")
    key = os.getenv("API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", "")
    console.print(f"来源: {src}")
    console.print(f"LLM_PROVIDER = {os.getenv('LLM_PROVIDER', 'anthropic')}")
    console.print(f"MODEL_NAME   = {os.getenv('MODEL_NAME', 'claude-opus-5')}")
    console.print(f"LLM_BASE_URL = {os.getenv('LLM_BASE_URL', '') or '(未设置)'}")
    console.print(
        f"API_KEY      = {settings_store.mask_secret(key) or '(未设置)'}")


if __name__ == "__main__":
    cli()
