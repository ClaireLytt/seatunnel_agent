from __future__ import annotations

import os
import sys

import click

from ..cli import _handle_error, _write_output, console
from ..sql_review.linter import DIALECTS as REVIEW_DIALECTS


@click.command()
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

    from ..sql_review import load_review_config

    verbose = ctx.obj.get("verbose", False)

    # ── collect review targets ──
    sources: list[tuple[str, str]] = []
    try:
        if sql:
            sources.append(("<inline>", sql))
        if sql_file:
            sources.append((sql_file, Path(sql_file).read_text(encoding="utf-8")))
        if paths or directory:
            from ..utils import collect_sql_files
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
            from ..sql_review.runner import changed_sql_files
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
        from ..sql_review.baseline import load_baseline
        try:
            baseline_prints = load_baseline(baseline)
        except ValueError as e:
            raise click.UsageError(str(e))

    # ── schema store (--ddl and/or --db) ──
    store = None
    db_executor = None
    if ddl:
        from ..text2sql.schema import SchemaStore
        store = SchemaStore.from_file(ddl)
    if db:
        m = re.fullmatch(r"([\w.\-]+):(\d+)/([\w.\-]+)", db.strip())
        if not m:
            raise click.UsageError("--db 格式应为 host:port/database")
        from ..sql_review.linter import EXECUTOR_DS_TYPES
        from ..text2sql.executor import DatabaseConfig, create_executor
        from ..text2sql.schema import SchemaStore
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
        from ..config import load_settings
        if ctx.obj.get("model"):
            os.environ["MODEL_NAME"] = ctx.obj["model"]
        if ctx.obj.get("provider"):
            os.environ["LLM_PROVIDER"] = ctx.obj["provider"]
        settings = load_settings()

    # ── review loop ──
    from ..sql_review import Severity, render_report, static_review_report
    from ..sql_review.rlog import ReviewLogger

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
                from ..sql_review import SQLReviewAgent
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
            from ..sql_review.explain import verify_with_explain
            verified = verify_with_explain(rep.findings, text, dialect, db_executor)
            if verified != rep.findings:
                rep.findings = verified
                report_md = render_report(rep)

        findings = rep.findings if rep else []
        baseline_entries.extend((label, f) for f in findings)

        suppressed = 0
        if baseline_prints and rep:
            from ..sql_review.baseline import split_by_baseline
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
            from ..sql_review import ReviewReport
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
                from ..sql_review.autofix import apply_static_fixes, describe_fixes
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
                from ..sql_review.fixer import generate_fix
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
        from ..sql_review.formats import results_to_json, results_to_sarif
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
        from ..sql_review.baseline import DEFAULT_BASELINE, save_baseline
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
        from ..sql_review.runner import severity_reached
        if severity_reached(all_findings, fail_on):
            console.print(f"\n[red]存在 {fail_on} 及以上级别的问题，审查未通过。[/red]")
            sys.exit(1)
    if failed:
        sys.exit(1)


@click.command(name="review-harness")
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

    from ..sql_review import load_review_config
    from ..sql_review.harness import (
        DEFAULT_LOG, diff_against_baseline, load_llm_cache,
        render_harness_report, run_harness,
    )

    try:
        review_config = load_review_config(rules)
    except ValueError as e:
        raise click.UsageError(str(e))

    store = None
    if ddl:
        from ..text2sql.schema import SchemaStore, parse_ddl
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


@click.command(name="review-stats")
@click.option("--recent", "-n", type=int, default=None,
              help="Only aggregate the most recent N reviews")
def review_stats(recent: int | None) -> None:
    """Show SQL review history statistics (from logs/sql_review.jsonl)."""
    from ..sql_review.rlog import ReviewLogger

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


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--sql", "-s", type=str, default=None, help="直接格式化一段 SQL")
@click.option("--dir", "-d", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="SQL 目录（递归扫描 *.sql）")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/...)")
@click.option("--write", "-w", "do_write", is_flag=True,
              help="将格式化结果写回文件（解析失败的文件绝不写）")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["error", "change"]),
              default=None,
              help="CI gate: error=解析失败; change=有文件需要格式化（black --check 式）")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def sqlfmt(
    paths: tuple[str, ...],
    sql: str | None,
    directory: str | None,
    dialect: str,
    do_write: bool,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """SQL 格式化 — sqlglot 确定性排版，--write 写回，--fail-on change 做 CI 门禁。

    PATHS: optional *.sql files or directories (as passed by pre-commit)."""
    import json as _json
    from pathlib import Path

    from ..sql_fmt import (
        FmtFileResult, fmt_dir, format_text,
        render_batch_markdown, render_markdown, result_to_dict,
    )
    from ..utils import collect_sql_files

    if not sql and not directory and not paths:
        raise click.UsageError("Provide --sql / --dir or positional paths")

    file_results: list[FmtFileResult] = []
    inline_result = None
    if sql:
        inline_result = format_text(sql, dialect=dialect)
    if directory:
        file_results.extend(fmt_dir(directory, dialect=dialect,
                                    write=do_write))
    for raw in paths:
        p = Path(raw)
        targets = collect_sql_files(p) if p.is_dir() else [p]
        for f in targets:
            text = f.read_text(encoding="utf-8", errors="replace")
            result = format_text(text, dialect=dialect, name=str(f))
            written = False
            if do_write and result.changed and not result.failed:
                f.write_text(result.formatted, encoding="utf-8")
                written = True
            file_results.append(FmtFileResult(
                path=str(f), result=result, written=written))

    if fmt == "json":
        payload: list = []
        if inline_result is not None:
            payload.append(result_to_dict(inline_result))
        payload.extend(r.to_dict() for r in file_results)
        text_out = _json.dumps(payload, ensure_ascii=False, indent=2)
        print(text_out)
    else:
        parts = []
        if inline_result is not None:
            parts.append(render_markdown(inline_result, lang))
        if file_results:
            parts.append(render_batch_markdown(file_results, lang))
        text_out = "\n\n---\n\n".join(parts)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    if fail_on:
        failed = (inline_result.failed if inline_result else 0) \
            + sum(r.result.failed for r in file_results)
        changed = (1 if inline_result is not None and inline_result.changed
                   else 0) \
            + sum(1 for r in file_results
                  if r.result.changed and not r.written)
        hit = failed > 0 or (fail_on == "change" and changed > 0)
        if hit:
            msg = ("存在解析失败的 SQL，检查未通过。" if fail_on == "error"
                   or changed == 0
                   else "存在需要格式化的 SQL，检查未通过。")
            if fmt == "json":
                print(msg, file=sys.stderr)
            else:
                console.print(f"\n[red]{msg}[/red]")
            sys.exit(1)


def register(cli) -> None:
    cli.add_command(review)
    cli.add_command(review_harness)
    cli.add_command(review_stats)
    cli.add_command(sqlfmt)
