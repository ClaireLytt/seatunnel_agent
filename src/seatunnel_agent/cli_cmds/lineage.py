from __future__ import annotations

import os
import sys

import click

from ..cli import (
    _ensure_utf8_stdio,
    _handle_error,
    _write_output,
    console,
)


@click.command()
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

    from ..data_lineage import LineageLogger, build_graph, load_lineage_config

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
        from ..data_lineage.openlineage import export_openlineage_file

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
        from ..config import load_settings
        from ..data_lineage import LineageAgent

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
    from ..data_lineage import render_report, static_lineage
    from ..data_lineage.render import (
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


@click.command(name="lineage-stats")
@click.option("--recent", "-n", type=int, default=20,
              help="Show the most recent N lineage queries")
def lineage_stats(recent: int) -> None:
    """Show lineage query history (from logs/lineage.jsonl)."""
    from ..data_lineage import LineageLogger

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


@click.command()
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

    from ..config_migrate import (
        migrate_dir, migrate_file, render_batch_markdown,
        render_migrate_markdown,
    )
    from ..config_migrate.migrator import LEVELS as MIG_LEVELS

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


@click.command(name="datadict")
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

    from ..data_lineage.dictionary import (
        add_llm_descriptions, build_dictionary, render_dictionary_markdown,
    )
    from ..data_lineage.loaders import build_graph

    graph, warnings = build_graph(sql_dir=sql_dir, use_cache=False,
                                  sql_dialect=sql_dialect)
    entries = build_dictionary(graph)
    if describe:
        try:
            from ..config import load_settings
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


@click.command(name="impact-stats")
@click.option("--recent", "-n", type=int, default=20, help="显示最近 N 条")
def impact_stats(recent: int) -> None:
    """变更影响分析历史与治理统计 (logs/impact.jsonl)。"""
    from collections import Counter

    from ..data_lineage.impact import ImpactLogger

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


@click.command(name="lineage-mcp")
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
    from ..data_lineage.mcp_server import create_mcp_server

    try:
        server = create_mcp_server(
            sql_dir=sql_dir, seatunnel_dir=seatunnel_dir, use_hive=use_hive,
            meta_table=meta_table, partition=partition, sql_dialect=sql_dialect,
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc))
    server.run()


@click.command()
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
    from ..data_lineage.governance import (
        analyze_governance,
        load_qlog_records,
        render_governance_markdown,
    )
    from ..data_lineage.loaders import build_graph

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


@click.command()
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

    from ..data_lineage.impact import (
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
        from ..data_lineage.impact import ImpactLogger
        ImpactLogger().log_impact(
            result, mode="git" if git_base else "dirs", source="cli",
            baseline=git_base or str(old_dir))
        worst = result.worst_level()
        if fail_on and worst and LEVELS.index(worst) <= LEVELS.index(fail_on):
            sys.exit(1)
    finally:
        if tmp_old is not None:
            shutil.rmtree(tmp_old, ignore_errors=True)


def register(cli) -> None:
    cli.add_command(lineage)
    cli.add_command(lineage_stats)
    cli.add_command(migrate)
    cli.add_command(datadict)
    cli.add_command(impact_stats)
    cli.add_command(lineage_mcp)
    cli.add_command(govern)
    cli.add_command(impact)
