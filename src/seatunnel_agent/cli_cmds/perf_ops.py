"""CLI entry points for the SQL performance suite (30-35).

Thin wrappers over the deterministic cores, same conventions as
pipeline_ops.py (shared _read/_emit/fail_check/track_history):

  seatunnel-agent sqlperf      -f plan.txt [--sql-file q.sql --llm]
  seatunnel-agent index-adv    -d workload/ [--ddl ddl.sql]
  seatunnel-agent sqlcost      --sql-file q.sql -f stats.json
                               [--fail-over-scan-gb N]
  seatunnel-agent slowquery    -f metrics.json [--baseline runs.jsonl]
                               [--history ledger.jsonl]
  seatunnel-agent dagconflict  -f scenario.json
"""

from __future__ import annotations

from pathlib import Path

import click

from ..common.cli_common import console  # noqa: F401  (rich tracebacks)
from .check_runner import emit_payload as _emit
from .check_runner import fail_check
from .check_runner import track_history as _track_history
from .pipeline_ops import _read


@click.command("sqlperf")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="EXPLAIN 输出文件")
@click.option("--text", type=str, default=None, help="内联 EXPLAIN 输出")
@click.option("--sql-file", "sql_path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="原 SQL 文件（配合 --llm 出改写草案）")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="按发现请求 LLM 改写 SQL（需配置 API key 与 --sql-file）")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
def sqlperf(path, text, sql_path, use_llm, lang, fmt, output) -> None:
    """执行计划分析 — EXPLAIN 文本 → join/shuffle/裁剪/下推发现与处方。"""
    from seatunnel_agent.agents.data.sql_perf import analyze, render_markdown

    result = analyze(_read(path, text, "EXPLAIN 输出"))
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        if not sql_path:
            raise click.UsageError("--llm 需配合 --sql-file")
        from seatunnel_agent.agents.data.sql_perf import advisor_llm
        from seatunnel_agent.agents.data.sql_perf.i18n import tp

        rewrite = advisor_llm.rewrite_sql(
            result, Path(sql_path).read_text(encoding="utf-8",
                                             errors="replace"), lang=lang)
        payload["rewrite"] = rewrite
        markdown += f"\n\n### {tp(lang, 'rpt_rewrite')}\n{rewrite}\n"
    _emit(payload, markdown, fmt, output)


@click.command("index-adv")
@click.option("--dir", "-d", "directory",
              type=click.Path(exists=True, file_okay=False), default=None,
              help="查询工作负载目录（递归 *.sql）")
@click.option("--text", type=str, default=None, help="内联多条 SQL")
@click.option("--ddl", "ddl_path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="建表 DDL 文件（可选）")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
def index_adv(directory, text, ddl_path, dialect, lang, fmt, output) -> None:
    """索引分区推荐 — 查询频次 → 分区/分桶/组合索引与 DDL 片段。"""
    from seatunnel_agent.agents.data.index_advisor import (
        analyze_workload,
        recommend,
        render_markdown,
    )
    from seatunnel_agent.common.utils import collect_sql_files

    if directory:
        files = collect_sql_files(directory)
        workload = "\n;\n".join(
            Path(p).read_text(encoding="utf-8", errors="replace")
            for p in files)
    elif text:
        workload = text
    else:
        raise click.UsageError("提供 --dir 或 --text")
    ddl = (Path(ddl_path).read_text(encoding="utf-8", errors="replace")
           if ddl_path else "")
    advice = recommend(analyze_workload(workload, dialect=dialect),
                       ddl_text=ddl)
    _emit(advice.to_dict(), render_markdown(advice, lang=lang), fmt, output)


@click.command("sqlcost")
@click.option("--sql-file", "sql_path", type=click.Path(exists=True, dir_okay=False),
              required=True, help="要估算的 SQL 文件")
@click.option("--file", "-f", "stats_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="表统计清单（JSON/CSV）")
@click.option("--fail-over-scan-gb", type=float, default=0.0,
              help="CI gate：预估扫描超过该 GB 数时 exit 1")
@click.option("--fail-over-shuffle-gb", type=float, default=0.0,
              help="CI gate：预估 shuffle 超过该 GB 数时 exit 1")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
def sqlcost(sql_path, stats_path, fail_over_scan_gb, fail_over_shuffle_gb,
            lang, fmt, output) -> None:
    """资源消耗预测 — SQL × 表统计 → 代价卡；可按预算挡 CI。"""
    from seatunnel_agent.agents.data.sql_cost import (
        estimate,
        parse_stats,
        render_markdown,
    )

    card = estimate(
        Path(sql_path).read_text(encoding="utf-8", errors="replace"),
        parse_stats(Path(stats_path).read_text(encoding="utf-8",
                                               errors="replace")))
    _emit(card.to_dict(), render_markdown(card, lang=lang), fmt, output)
    problems: list[str] = []
    scan_gb = card.scan_bytes / (1 << 30)
    shuffle_gb = card.shuffle_bytes / (1 << 30)
    if fail_over_scan_gb and scan_gb > fail_over_scan_gb:
        problems.append(f"BUDGET scan {scan_gb:.1f} GB > "
                        f"{fail_over_scan_gb:g} GB")
    if fail_over_shuffle_gb and shuffle_gb > fail_over_shuffle_gb:
        problems.append(f"BUDGET shuffle {shuffle_gb:.1f} GB > "
                        f"{fail_over_shuffle_gb:g} GB")
    if problems:
        fail_check("\n".join(problems), fmt)


@click.command("slowquery")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="执行指标 JSON 文件")
@click.option("--text", type=str, default=None, help="内联指标 JSON")
@click.option("--baseline", "baseline_path",
              type=click.Path(exists=True, dir_okay=False), default=None,
              help="历史基线 jsonl")
@click.option("--history", "history_path", type=click.Path(dir_okay=False),
              default=None,
              help="慢查询台账：主因/占比/回归倍数追加到该 jsonl")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
def slowquery(path, text, baseline_path, history_path, lang, fmt,
              output) -> None:
    """慢查询根因 — 指标 × 基线 → 排序根因与处方；--history 记台账。"""
    from seatunnel_agent.agents.data.slow_query import (
        diagnose,
        parse_baseline,
        parse_metrics,
        render_markdown,
    )

    baseline = (Path(baseline_path).read_text(encoding="utf-8",
                                              errors="replace")
                if baseline_path else "")
    diag = diagnose(parse_metrics(_read(path, text, "执行指标")),
                    parse_baseline(baseline))
    _emit(diag.to_dict(), render_markdown(diag, lang=lang), fmt, output)
    if history_path:
        top = diag.causes[0] if diag.causes else None
        _track_history(history_path, {
            "duration_s": diag.duration_s,
            "regression": diag.regression,
            "causes": len(diag.causes),
            "top_share": round(top.share, 3) if top else 0.0,
        }, worse_key="duration_s")


@click.command("dagconflict")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="场景 JSON 文件")
@click.option("--text", type=str, default=None, help="内联场景 JSON")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
def dagconflict(path, text, lang, fmt, output) -> None:
    """并发冲突检测 — 多 DAG 场景 → 超容窗/写写冲突/错峰建议。"""
    from seatunnel_agent.agents.data.dag_conflict import (
        parse_scenario,
        render_markdown,
        simulate,
    )

    result = simulate(parse_scenario(_read(path, text, "场景 JSON")))
    _emit(result.to_dict(), render_markdown(result, lang=lang), fmt, output)


def register(cli) -> None:
    cli.add_command(sqlperf)
    cli.add_command(index_adv)
    cli.add_command(sqlcost)
    cli.add_command(slowquery)
    cli.add_command(dagconflict)
