from __future__ import annotations

import os
import sys

import click

from seatunnel_agent.agents.data.sql_transpile import DIALECTS as TRANSPILE_DIALECTS

from ..common.cli_common import _handle_error, console


@click.command()
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
@click.option("--mask", "emit_mask", is_flag=True, default=False,
              help="输出处置方案：为命中列生成脱敏视图 SQL（代替扫描报告）")
@click.option("--min-confidence", type=click.Choice(["low", "high"]),
              default="low", show_default=True,
              help="--mask 时纳入的最低置信度（high 跳过弱命中如裸 name 列）")
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
    emit_mask: bool,
    min_confidence: str,
) -> None:
    """敏感数据扫描 — 命名规则 × 字段血缘，静态识别 PII 列及未脱敏扩散。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.data.pii_scan import (
        DEFAULT_RULES,
        load_extra_rules,
        render_markdown,
        report_to_dict,
        scan_dir,
        scan_files,
        scan_sql_text,
    )

    from .check_runner import (
        SEVERITY_RANK,
        CheckSpec,
        analyze_input,
        emit_report,
        fail_check,
        save_output,
        severity_gate,
    )

    rules = list(DEFAULT_RULES)
    if rules_path:
        try:
            rules += load_extra_rules(rules_path)
        except ValueError as exc:
            raise click.ClickException(str(exc))

    spec = CheckSpec(
        analyze_dir=scan_dir,
        analyze_file=scan_files,
        analyze_sql=scan_sql_text,
        render=render_markdown,
        to_dict=report_to_dict,
        error_label="扫描失败",
    )
    report = analyze_input(spec, directory, sql, sql_file, dialect,
                           rules=rules)

    if emit_mask:
        from seatunnel_agent.agents.data.pii_scan import (
            build_mask_plan,
            collect_columns_from_ddl,
            render_mask_sql,
        )

        if directory:
            sources = sorted(Path(directory).rglob("*.sql"))
            text = "\n;\n".join(p.read_text(encoding="utf-8")
                                for p in sources)
        elif sql_file:
            text = Path(sql_file).read_text(encoding="utf-8")
        else:
            text = sql or ""
        inventory, _ = collect_columns_from_ddl(text, dialect)
        plan = build_mask_plan(report, inventory, min_confidence)
        if fmt == "json":
            text_out = _json.dumps(plan.to_dict(),
                                   ensure_ascii=False, indent=2)
            print(text_out)
        else:
            text_out = render_mask_sql(plan)
            console.print(text_out, markup=False)
        save_output(text_out, output)
        if fail_on:
            # treatment-aware gate: findings the generated views already
            # cover are remediated — only UNCOVERED ones can fail the CI
            worst_sev = plan.coverage.worst_uncovered()
            worst = SEVERITY_RANK[worst_sev] if worst_sev else 0
            if worst >= SEVERITY_RANK[fail_on]:
                fail_check(f"存在 {fail_on} 及以上级别且脱敏方案未覆盖的敏感列，"
                           "检查未通过。", fmt)
    else:
        emit_report(spec, report, lang, fmt, output)
        if fail_on:
            msg = severity_gate(
                report.findings, fail_on,
                f"存在 {fail_on} 及以上级别的敏感列风险，检查未通过。")
            if msg:
                fail_check(msg, fmt)


@click.command()
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

    from seatunnel_agent.agents.data.log_inspect import (
        render_markdown,
        report_to_dict,
        scan_dir,
        scan_files,
    )
    from seatunnel_agent.agents.data.log_inspect.clusterer import DEFAULT_PATTERNS

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


@click.command(name="schemadiff")
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
def schemadiff(
    old_path: str,
    new_path: str,
    dialect: str,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """Schema 漂移检查 — 对比两份 DDL 快照，按破坏/风险/提示分级报告变更。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.data.schema_drift import (
        diff_paths,
        render_markdown,
        report_to_dict,
    )

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


@click.command()
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

    from seatunnel_agent.agents.data.sql_testgen import (
        generate,
        render_markdown,
        result_to_dict,
        validate_with_sqlite,
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


@click.command()
@click.option("--config", "-c", "config_text", type=str, default=None,
              help="直接检查一段 HOCON 配置")
@click.option("--file", "-f", "conf_file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="检查单个 .conf 文件")
@click.option("--dir", "-d", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="配置目录（递归扫描 *.conf）")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["error", "warn"]),
              default=None, help="CI gate: exit 1 when findings at/above this level exist")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def conflint(
    config_text: str | None,
    conf_file: str | None,
    directory: str | None,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """SeaTunnel 配置深度检查 — 参数级 lint，未知参数带「是不是想写」建议。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.data.config_lint import (
        lint_dir,
        lint_file,
        lint_text,
        render_batch_markdown,
        render_markdown,
        result_to_dict,
    )

    if not config_text and not conf_file and not directory:
        raise click.UsageError("Provide --config / --file / --dir")

    if directory:
        results = lint_dir(directory)
        md = render_batch_markdown(results, lang)
    elif conf_file:
        results = [lint_file(conf_file)]
        md = render_markdown(results[0], lang)
    else:
        results = [lint_text(config_text)]
        md = render_markdown(results[0], lang)

    if fmt == "json":
        text_out = _json.dumps([result_to_dict(r, lang) for r in results],
                               ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = md
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    if fail_on:
        rank = {"info": 1, "warn": 2, "error": 3}
        threshold = rank[fail_on]
        worst = max((rank[f.severity] for r in results for f in r.findings),
                    default=0)
        if worst >= threshold:
            msg = f"存在 {fail_on} 及以上级别的配置问题，检查未通过。"
            if fmt == "json":
                print(msg, file=sys.stderr)
            else:
                console.print(f"\n[red]{msg}[/red]")
            sys.exit(1)


@click.command()
@click.option("--sql-dir", "-d", type=click.Path(exists=True, file_okay=False),
              required=True, help="SQL 目录（递归扫描 *.sql）")
@click.option("--seatunnel-dir", type=click.Path(exists=True, file_okay=False),
              default=None, help="可选：合并 SeaTunnel 配置目录的 source→sink 血缘")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/...)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["error", "warn"]),
              default=None, help="CI gate: exit 1 when findings at/above this level exist")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def dagcheck(
    sql_dir: str,
    seatunnel_dir: str | None,
    dialect: str,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """调度 DAG 体检 — 环/断链/死作业检测 + 执行分批与关键路径。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.data.dag_check import (
        check_sql_dir,
        render_markdown,
        report_to_dict,
    )

    report = check_sql_dir(sql_dir, dialect=dialect,
                           seatunnel_dir=seatunnel_dir)

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
        rank = {"info": 1, "warn": 2, "error": 3}
        threshold = rank[fail_on]
        worst = max((rank[f.severity] for f in report.findings), default=0)
        if worst >= threshold:
            msg = f"存在 {fail_on} 及以上级别的调度隐患，检查未通过。"
            if fmt == "json":
                print(msg, file=sys.stderr)
            else:
                console.print(f"\n[red]{msg}[/red]")
            sys.exit(1)


@click.command()
@click.option("--sql-dir", "-d", type=click.Path(exists=True, file_okay=False),
              required=True, help="SQL 目录（递归扫描 *.sql）")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/...)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["high", "medium"]),
              default=None, help="CI gate: exit 1 when conflicts at/above this level exist")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def metricdiff(
    sql_dir: str,
    dialect: str,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """指标口径一致性检查 — 同名输出列在不同作业里的定义冲突。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.data.metric_diff import (
        check_sql_dir,
        render_markdown,
        report_to_dict,
    )

    report = check_sql_dir(sql_dir, dialect=dialect)

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
        rank = {"medium": 1, "high": 2}
        threshold = rank[fail_on]
        worst = max((rank[c.severity] for c in report.conflicts), default=0)
        if worst >= threshold:
            msg = f"存在 {fail_on} 及以上级别的口径冲突，检查未通过。"
            if fmt == "json":
                print(msg, file=sys.stderr)
            else:
                console.print(f"\n[red]{msg}[/red]")
            sys.exit(1)


@click.command()
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

    from seatunnel_agent.agents.data.sql_transpile import (
        batch_to_dict,
        render_batch_markdown,
        render_markdown,
        result_to_dict,
        translate,
        transpile_dir,
    )
    from seatunnel_agent.agents.data.sql_transpile.transpiler import LEVELS

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
                    from seatunnel_agent.agents.data.sql_transpile.advisor import (
                        advisable_issues,
                        generate_advice,
                    )

                    from ..common.config import load_settings
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
    except Exception as e:
        _handle_error(e, verbose)


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--text", "-t", default=None, help="直接扫描一段文本")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["high", "medium", "low"]),
              default=None,
              help="CI gate: 达到该严重度及以上的发现时退出 1")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
def secretscan(
    paths: tuple[str, ...],
    text: str | None,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """敏感凭证扫描 — 云厂商 token / 私钥 / 明文密码 / 高熵串,预览脱敏。

    PATHS: 文件或目录(pre-commit 风格);.secretscan.yaml 可配置豁免,
    单行加 secretscan:ignore 跳过。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.devops.secret_scan import (
        ScanResult,
        check_fail,
        render_markdown,
        scan_paths,
        scan_text,
    )

    if not text and not paths:
        raise click.UsageError("Provide --text or positional paths")

    if text:
        result = ScanResult(findings=scan_text(text), files_scanned=1)
    else:
        try:
            result = scan_paths(list(paths))
        except ValueError as exc:  # malformed .secretscan.yaml
            console.print(f"[red]{exc}[/red]")
            sys.exit(2)

    if fmt == "json":
        text_out = _json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_markdown(result, lang)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    if fail_on and check_fail(result, fail_on):
        msg = f"存在 {fail_on} 及以上严重度的疑似凭证,检查未通过。"
        if fmt == "json":
            print(msg, file=sys.stderr)
        else:
            console.print(f"\n[red]{msg}[/red]")
        sys.exit(1)


@click.command()
@click.option("--path", "-p", default=".", show_default=True,
              type=click.Path(exists=True, file_okay=False),
              help="项目根目录(读 pyproject.toml 与 requirements*.txt)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["high", "medium"]),
              default=None,
              help="CI gate: 达到该严重度及以上的发现时退出 1")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
def depcheck(
    path: str,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """依赖体检 — 声明 vs 实装、版本钉、License 清单(全离线)。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.devops.dep_check import (
        check,
        check_fail,
        collect_from_path,
        render_markdown,
    )

    try:
        reqs = collect_from_path(path)
    except ValueError as exc:  # malformed pyproject
        console.print(f"[red]{exc}[/red]")
        sys.exit(2)
    if not reqs:
        console.print("[red]该目录下没有 pyproject.toml / requirements*.txt[/red]")
        sys.exit(2)
    report = check(reqs)

    if fmt == "json":
        text_out = _json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_markdown(report, lang)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    if fail_on and check_fail(report, fail_on):
        msg = f"存在 {fail_on} 及以上严重度的依赖问题,检查未通过。"
        if fmt == "json":
            print(msg, file=sys.stderr)
        else:
            console.print(f"\n[red]{msg}[/red]")
        sys.exit(1)


@click.command()
@click.argument("logs", nargs=-1, type=click.Path(exists=True, dir_okay=False))
@click.option("--runs", "runs_file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="运行元数据 JSON 文件(flaky/时长分析)")
@click.option("--gh", "gh_repo", default=None,
              help="用 gh api 拉取 owner/repo 最近运行元数据(需 gh 登录)")
@click.option("--limit", default=30, show_default=True,
              type=click.IntRange(1, 100), help="--gh 拉取的运行数量")
@click.option("--top", default=10, show_default=True,
              type=click.IntRange(1, 50), help="根因聚类 Top-N")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["flaky"]), default=None,
              help="CI gate: flaky=发现同一提交又过又挂的工作流时退出 1")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
@click.option("--notify", "do_notify", is_flag=True,
              help="NOTIFY_WEBHOOK_URL webhook alert on flaky workflows")
def ciinspect(
    logs: tuple[str, ...],
    runs_file: str | None,
    gh_repo: str | None,
    limit: int,
    top: int,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
    do_notify: bool,
) -> None:
    """CI 日志诊断 — 失败日志根因聚类 + flaky 识别 + 时长漂移。

    LOGS: 失败作业日志文件(gh run view --log-failed 的输出即可)。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.devops.ci_inspect import (
        analyze,
        collect_gh_runs,
        render_markdown,
    )

    runs_text = None
    if runs_file:
        runs_text = Path(runs_file).read_text(encoding="utf-8")
    elif gh_repo:
        try:
            runs_text = collect_gh_runs(gh_repo, limit)
        except RuntimeError as exc:
            console.print(f"[red]gh 拉取失败: {exc}[/red]")
            sys.exit(2)
    if not logs and not runs_text:
        raise click.UsageError("Provide log files, --runs or --gh")

    # key by basename for readable reports, but never silently drop a
    # same-named log from another directory
    log_map: dict[str, str] = {}
    for p in logs:
        name = Path(p).name
        key = name if name not in log_map else str(p)
        log_map[key] = Path(p).read_text(encoding="utf-8", errors="replace")
    try:
        report = analyze(logs=log_map, runs_text=runs_text, top=top)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(2)

    if fmt == "json":
        text_out = _json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_markdown(report, lang)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    if do_notify and report.runs.flaky:
        from ..common.notify import send as notify_send
        notify_send("CI flaky alert",
                    "; ".join(f"{f['workflow']} @ {f['head_sha']}"
                              for f in report.runs.flaky[:10]))

    if fail_on == "flaky" and report.runs.flaky:
        msg = "发现 flaky 工作流(同一提交又过又挂),检查未通过。"
        if fmt == "json":
            print(msg, file=sys.stderr)
        else:
            console.print(f"\n[red]{msg}[/red]")
        sys.exit(1)


@click.command()
@click.option("--dir", "-d", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="SQL 目录（递归扫描 *.sql）")
@click.option("--sql", type=str, default=None, help="直接分析一段 SQL")
@click.option("--file", "-f", "sql_file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="分析单个 SQL 文件")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/...)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--exempt", "exempt_path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="孤儿豁免清单 YAML(tables: [通配模式],外部 BI 直读的表)")
@click.option("--fail-on", type=click.Choice(["orphans", "dead", "dangling", "any"]),
              default=None, help="CI gate: exit 1 when the chosen kind exists")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def hygiene(
    directory: str | None,
    sql: str | None,
    sql_file: str | None,
    dialect: str,
    exempt_path: str | None,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """数仓卫生检查 — 血缘驱动的死重报告：只写不读的表、无人取的列、悬空 DDL。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.lineage_hygiene import (
        analyze_dir,
        analyze_sql_text,
        render_markdown,
    )
    from seatunnel_agent.agents.data.lineage_hygiene.analyzer import analyze_files
    from seatunnel_agent.agents.data.lineage_hygiene.history import HygieneLogger

    from .check_runner import CheckSpec, run_check

    exempt: list[str] = []
    if exempt_path:
        import yaml

        try:
            raw = yaml.safe_load(Path(exempt_path).read_text(
                encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise click.ClickException(f"无法读取豁免清单 {exempt_path}: {exc}")
        items = raw.get("tables") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            raise click.ClickException(
                f"{exempt_path}: 期望顶层为 tables: [...] 列表")
        exempt = [str(x) for x in items]

    def _gate(report, fail_on: str) -> str | None:
        c = report.counts()
        hit = {
            "orphans": c["orphan_outputs"],
            "dead": c["dead_columns"],
            "dangling": c["dangling_defs"],
            "any": c["total"],
        }[fail_on]
        if hit:
            return f"存在 {fail_on} 类数仓死重（{hit} 项），检查未通过。"
        return None

    spec = CheckSpec(
        analyze_dir=analyze_dir,
        analyze_file=analyze_files,
        analyze_sql=analyze_sql_text,
        render=render_markdown,
        to_dict=lambda report, lang: report.to_dict(),
        error_label="分析失败",
        gate=_gate,
        log_run=lambda report: HygieneLogger().log_run(report, source="cli"),
    )
    run_check(spec, directory=directory, sql=sql, sql_file=sql_file,
              dialect=dialect, lang=lang, fmt=fmt, output=output,
              fail_on=fail_on, exempt=exempt)


@click.command()
@click.option("--dir", "-d", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="SQL 目录（递归扫描 *.sql）")
@click.option("--sql", type=str, default=None, help="直接检查一段 DDL")
@click.option("--file", "-f", "sql_file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="检查单个 SQL 文件")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/...)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["high", "medium", "low"]),
              default=None, help="CI gate: exit 1 when findings at/above this level exist")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def metaquality(
    directory: str | None,
    sql: str | None,
    sql_file: str | None,
    dialect: str,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """元数据质量体检 — 注释覆盖率、分层命名错配、金额浮点/日期裸 STRING 反模式。"""
    from seatunnel_agent.agents.data.metadata_quality import (
        check_dir,
        check_sql_text,
        render_markdown,
    )
    from seatunnel_agent.agents.data.metadata_quality.checker import check_files
    from seatunnel_agent.agents.data.metadata_quality.history import (
        MetaQualityLogger,
    )

    from .check_runner import CheckSpec, run_check, severity_gate

    spec = CheckSpec(
        analyze_dir=check_dir,
        analyze_file=check_files,
        analyze_sql=check_sql_text,
        render=render_markdown,
        to_dict=lambda report, lang: report.to_dict(),
        error_label="检查失败",
        gate=lambda report, fail_on: severity_gate(
            report.findings, fail_on,
            f"存在 {fail_on} 及以上级别的元数据问题，检查未通过。"),
        log_run=lambda report: MetaQualityLogger().log_run(report,
                                                           source="cli"),
    )
    run_check(spec, directory=directory, sql=sql, sql_file=sql_file,
              dialect=dialect, lang=lang, fmt=fmt, output=output,
              fail_on=fail_on)


@click.command()
@click.option("--dir", "-d", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="SQL 目录（递归扫描 *.sql）")
@click.option("--sql", type=str, default=None, help="直接校验一段 DDL")
@click.option("--file", "-f", "sql_file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="校验单个 SQL 文件")
@click.option("--contract", "-c", "contract_path",
              type=click.Path(exists=True, dir_okay=False),
              help="契约 YAML（tables: 声明列/类型/注释要求/分区键）")
@click.option("--init", "init_mode", is_flag=True, default=False,
              help="从现有 DDL 反向生成契约 YAML 底稿（配 -o 落盘）")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/...)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["high", "medium", "low"]),
              default=None, help="CI gate: exit 1 when violations at/above this level exist")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def contract(
    directory: str | None,
    sql: str | None,
    sql_file: str | None,
    contract_path: str | None,
    init_mode: bool,
    dialect: str,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """数据契约校验 — YAML 声明的表承诺 vs 实际 DDL，违约分级报出。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.contract_check import (
        check_dir,
        check_files,
        check_sql_text,
        parse_contract,
        render_markdown,
    )
    from seatunnel_agent.agents.data.contract_check.history import (
        ContractLogger,
    )

    from .check_runner import CheckSpec, run_check, severity_gate

    if init_mode:
        from seatunnel_agent.agents.data.contract_check.bootstrap import (
            generate_contract,
            generate_from_dir,
        )

        if not directory and not sql and not sql_file:
            raise click.UsageError("Provide --dir / --sql / --file")
        try:
            if directory:
                draft = generate_from_dir(directory, dialect=dialect)
            elif sql_file:
                draft = generate_contract(
                    Path(sql_file).read_text(encoding="utf-8"),
                    dialect=dialect)
            else:
                draft = generate_contract(sql or "", dialect=dialect)
        except ValueError as exc:
            raise click.ClickException(str(exc))
        print(draft, end="")
        if output:
            Path(output).write_text(draft, encoding="utf-8")
            console.print(f"[dim]契约底稿已保存: {output}[/dim]")
        return

    if not contract_path:
        raise click.UsageError("Provide --contract (or use --init to "
                               "generate a draft)")
    contract_text = Path(contract_path).read_text(encoding="utf-8")
    try:
        parse_contract(contract_text)
    except ValueError as exc:
        raise click.ClickException(f"契约格式错误: {exc}")

    spec = CheckSpec(
        analyze_dir=check_dir,
        analyze_file=check_files,
        analyze_sql=check_sql_text,
        render=render_markdown,
        to_dict=lambda report, lang: report.to_dict(),
        error_label="校验失败",
        gate=lambda report, fail_on: severity_gate(
            report.findings, fail_on,
            f"存在 {fail_on} 及以上级别的契约违约，检查未通过。"),
        log_run=lambda report: ContractLogger().log_run(report, source="cli"),
    )
    run_check(spec, directory=directory, sql=sql, sql_file=sql_file,
              dialect=dialect, lang=lang, fmt=fmt, output=output,
              fail_on=fail_on, contract=contract_text)


@click.command()
@click.option("--dir", "-d", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="SQL 目录（递归扫描 *.sql）")
@click.option("--sql", type=str, default=None, help="直接扫描一段 SQL")
@click.option("--file", "-f", "sql_file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="扫描单个 SQL 文件")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/...)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["high", "medium"]),
              default=None, help="CI gate: exit 1 when findings at/above this level exist")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def grants(
    directory: str | None,
    sql: str | None,
    sql_file: str | None,
    dialect: str,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """权限面扫描 — GRANT/REVOKE 净面,公开授权/宽权限/敏感表外授分级。"""
    from seatunnel_agent.agents.data.grant_scan import (
        render_markdown,
        scan_dir,
        scan_files,
        scan_sql_text,
    )
    from seatunnel_agent.agents.data.grant_scan.history import GrantsLogger

    from .check_runner import CheckSpec, run_check, severity_gate

    spec = CheckSpec(
        analyze_dir=scan_dir,
        analyze_file=scan_files,
        analyze_sql=scan_sql_text,
        render=render_markdown,
        to_dict=lambda report, lang: report.to_dict(),
        error_label="扫描失败",
        gate=lambda report, fail_on: severity_gate(
            report.findings, fail_on,
            f"存在 {fail_on} 及以上级别的权限面风险，检查未通过。"),
        log_run=lambda report: GrantsLogger().log_run(report, source="cli"),
    )
    run_check(spec, directory=directory, sql=sql, sql_file=sql_file,
              dialect=dialect, lang=lang, fmt=fmt, output=output,
              fail_on=fail_on)


@click.command(name="ddlguard")
@click.option("--dir", "-d", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="SQL 目录（递归扫描 *.sql）")
@click.option("--sql", type=str, default=None, help="直接扫描一段迁移 SQL")
@click.option("--file", "-f", "sql_file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="扫描单个迁移脚本")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/...)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["high", "medium"]),
              default=None, help="CI gate: exit 1 when operations at/above this level exist")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
@click.option("--undo", "-u", "undo_path", type=click.Path(), default=None,
              help="把回滚脚本另存为 SQL 文件")
def ddlguard(
    directory: str | None,
    sql: str | None,
    sql_file: str | None,
    dialect: str,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
    undo_path: str | None,
) -> None:
    """迁移守卫 — 危险 DDL 分级(删表/收窄 high),并生成回滚脚本。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.ddl_guard import (
        render_markdown,
        scan_dir,
        scan_files,
        scan_sql_text,
    )
    from seatunnel_agent.agents.data.ddl_guard.history import DdlGuardLogger

    from .check_runner import CheckSpec, run_check, severity_gate

    def _save_undo(report) -> None:
        # runs before the gate: the rollback must land even when CI fails
        if undo_path and report.undo_sql:
            Path(undo_path).write_text(report.undo_sql, encoding="utf-8")
            console.print(f"[dim]回滚脚本已保存: {undo_path}[/dim]")
        DdlGuardLogger().log_run(report, source="cli")

    spec = CheckSpec(
        analyze_dir=scan_dir,
        analyze_file=scan_files,
        analyze_sql=scan_sql_text,
        render=render_markdown,
        to_dict=lambda report, lang: report.to_dict(),
        error_label="扫描失败",
        gate=lambda report, fail_on: severity_gate(
            report.findings, fail_on,
            f"存在 {fail_on} 及以上级别的危险 DDL 操作，检查未通过。"),
        log_run=_save_undo,
    )
    run_check(spec, directory=directory, sql=sql, sql_file=sql_file,
              dialect=dialect, lang=lang, fmt=fmt, output=output,
              fail_on=fail_on)


@click.command(name="hygiene-stats")
@click.option("--recent", "-n", type=int, default=20, help="显示最近 N 条")
def hygiene_stats(recent: int) -> None:
    """数仓卫生历史与趋势 (logs/hygiene.jsonl)。"""
    from seatunnel_agent.agents.data.lineage_hygiene.history import (
        HygieneLogger,
    )

    records = HygieneLogger().recent(recent)
    if not records:
        console.print("[yellow]还没有数仓卫生检查记录。[/yellow]")
        return
    console.print("[bold]数仓卫生检查历史[/bold]")
    for r in records:
        c = r.get("counts") or {}
        console.print(
            f"  {r.get('timestamp', '')}  [{r.get('source', '')}] "
            f"表={r.get('tables_seen', 0)}  孤儿={c.get('orphan_outputs', 0)} "
            f"死列={c.get('dead_columns', 0)} 悬空={c.get('dangling_defs', 0)} "
            f"豁免={r.get('exempted', 0)}")
    first, last = records[0], records[-1]
    fo = (first.get("counts") or {}).get("orphan_outputs", 0)
    lo = (last.get("counts") or {}).get("orphan_outputs", 0)
    console.print(f"\n[bold]趋势[/bold] 孤儿表 {fo} → {lo}"
                  f"(最近 {len(records)} 次)")


@click.command(name="metaquality-stats")
@click.option("--recent", "-n", type=int, default=20, help="显示最近 N 条")
def metaquality_stats(recent: int) -> None:
    """元数据质量历史与趋势 (logs/metaquality.jsonl)。"""
    from seatunnel_agent.agents.data.metadata_quality.history import (
        MetaQualityLogger,
    )

    records = MetaQualityLogger().recent(recent)
    if not records:
        console.print("[yellow]还没有元数据质量检查记录。[/yellow]")
        return
    console.print("[bold]元数据质量检查历史[/bold]")
    for r in records:
        c = r.get("counts") or {}
        console.print(
            f"  {r.get('timestamp', '')}  [{r.get('source', '')}] "
            f"表={r.get('tables_checked', 0)}  high={c.get('high', 0)} "
            f"medium={c.get('medium', 0)} low={c.get('low', 0)}  "
            f"注释覆盖={r.get('comment_pct', 100)}%")
    first, last = records[0], records[-1]
    console.print(f"\n[bold]趋势[/bold] 注释覆盖 "
                  f"{first.get('comment_pct', 100)}% → "
                  f"{last.get('comment_pct', 100)}%(最近 {len(records)} 次)")


def register(cli) -> None:
    cli.add_command(pii)
    cli.add_command(hygiene)
    cli.add_command(metaquality)
    cli.add_command(contract)
    cli.add_command(grants)
    cli.add_command(ddlguard)
    cli.add_command(hygiene_stats)
    cli.add_command(metaquality_stats)
    cli.add_command(loginspect)
    cli.add_command(schemadiff)
    cli.add_command(testgen)
    cli.add_command(conflint)
    cli.add_command(dagcheck)
    cli.add_command(metricdiff)
    cli.add_command(transpile)
    cli.add_command(secretscan)
    cli.add_command(depcheck)
    cli.add_command(ciinspect)
