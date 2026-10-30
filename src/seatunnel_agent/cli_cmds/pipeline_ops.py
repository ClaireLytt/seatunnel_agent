"""CLI entry points for the pipeline-ops agent suite (25-29).

Thin wrappers over the deterministic cores — same inputs as the web
pages and MCP tools: a file or inline text in, markdown or JSON out.

  seatunnel-agent dagopt       -f dag.json
  seatunnel-agent rerun        -f dag.json --failed clean_orders
  seatunnel-agent backfill-sql -f spec.json
  seatunnel-agent sync-strategy -f tables.json
  seatunnel-agent pipe-migrate -d legacy_scripts/
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from ..common.cli_common import console


def _read(path: str | None, text: str | None, what: str) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    if text:
        return text
    raise click.UsageError(f"提供 --file 或 --text（{what}）")


def _emit(result_dict: dict, markdown: str, fmt: str,
          output: str | None) -> None:
    text_out = (json.dumps(result_dict, ensure_ascii=False, indent=2)
                if fmt == "json" else markdown)
    if fmt == "json":
        print(text_out)
    else:
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")


_COMMON = [
    click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
                 show_default=True, help="Report language"),
    click.option("--format", "-F", "fmt",
                 type=click.Choice(["markdown", "json"]),
                 default="markdown", help="Report format"),
    click.option("--output", "-o", type=click.Path(), default=None,
                 help="Save report to file"),
]


def _common(fn):
    for deco in reversed(_COMMON):
        fn = deco(fn)
    return fn


@click.command("dagopt")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="任务依赖图（JSON tasks/edges、DOT 或文本行）")
@click.option("--text", type=str, default=None, help="内联依赖图")
@click.option("--deadline", type=float, default=0.0,
              help="SLA 时长 — 判定是否满足并给出最小提速集合")
@_common
def dagopt(path, text, deadline, lang, fmt, output) -> None:
    """DAG 依赖优化 — 冗余串行边、并行批次、关键路径与加速比。"""
    from seatunnel_agent.agents.data.dag_optimize import (
        optimize,
        parse_dag,
        render_markdown,
    )

    result = optimize(parse_dag(_read(path, text, "依赖图")),
                      deadline=deadline)
    _emit(result.to_dict(), render_markdown(result, lang=lang), fmt, output)


@click.command("rerun")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="任务依赖图（JSON tasks/edges、DOT 或文本行）")
@click.option("--text", type=str, default=None, help="内联依赖图")
@click.option("--failed", default="", help="失败任务名，逗号分隔")
@click.option("--succeeded", default="", help="已成功任务名，逗号分隔")
@click.option("--statuses", default="",
              help='调度器状态导出（{"task":"state"} JSON 或 task=state 行）')
@click.option("--cmd", default="", help="命令模板，用 {task} 占位")
@_common
def rerun(path, text, failed, succeeded, statuses, lang, fmt, output,
          cmd) -> None:
    """任务重跑规划 — 失败节点 × 下游闭包的最小重跑批次与影响面。"""
    from seatunnel_agent.agents.data.rerun_plan import (
        parse_dag,
        parse_statuses,
        plan_rerun,
        render_markdown,
    )

    graph = parse_dag(_read(path, text, "依赖图"))
    if statuses.strip():
        failed_list, ok_list = parse_statuses(statuses)
        result = plan_rerun(graph, failed_list, ok_list)
    elif failed.strip():
        result = plan_rerun(graph, failed, succeeded)
    else:
        raise click.UsageError("提供 --failed 或 --statuses")
    _emit(result.to_dict(),
          render_markdown(result, lang=lang, cmd_template=cmd), fmt, output)


@click.command("backfill-sql")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="补数规格 JSON 文件")
@click.option("--text", type=str, default=None, help="内联规格 JSON")
@click.option("--plan", type=str, default=None,
              help="补数计划器的计划 JSON — 输出逐表规格骨架（代替生成 SQL）")
@_common
def backfill_sql(path, text, plan, lang, fmt, output) -> None:
    """回溯补数 SQL — 逐分区幂等语句与前后置校验；--plan 出规格骨架。"""
    from seatunnel_agent.agents.data.backfill_sql import (
        generate,
        parse_spec,
        render_markdown,
        specs_from_plan,
    )

    if plan:
        from seatunnel_agent.agents.data.backfill_sql.tools import (
            backfill_specs,
        )

        specs = specs_from_plan(plan)
        _emit({"specs": specs}, backfill_specs(plan, lang=lang), fmt, output)
        return
    result = generate(parse_spec(_read(path, text, "补数规格")))
    _emit(result.to_dict(), render_markdown(result, lang=lang), fmt, output)


def _safe_conf_name(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name) + ".conf"


def _emit_confs(out_dir: str, items: list[tuple[str, str]]) -> None:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    for name, conf in items:
        dest = target / _safe_conf_name(name)
        dest.write_text(conf + "\n", encoding="utf-8")
        console.print(f"[dim]已写入: {dest}[/dim]")
    console.print(f"{len(items)} 个配置骨架已落盘 → {target}")


@click.command("sync-strategy")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="表特征清单（JSON/CSV）或 CREATE TABLE DDL")
@click.option("--text", type=str, default=None, help="内联清单或 DDL")
@click.option("--emit-configs", "emit_dir", type=click.Path(file_okay=False),
              default=None, help="把每张表的 SeaTunnel 配置骨架写到该目录")
@_common
def sync_strategy(path, text, emit_dir, lang, fmt, output) -> None:
    """增量同步策略 — 全量/增量/CDC 推荐、风险与 SeaTunnel 配置骨架。"""
    from seatunnel_agent.agents.data.sync_strategy import (
        parse_tables,
        recommend,
        render_markdown,
    )

    result = recommend(parse_tables(_read(path, text, "表特征清单")))
    _emit(result.to_dict(), render_markdown(result, lang=lang), fmt, output)
    if emit_dir:
        _emit_confs(emit_dir, [(r.table, r.config)
                               for r in result.recommendations if r.config])


@click.command("pipe-migrate")
@click.option("--dir", "-d", "directory",
              type=click.Path(exists=True, file_okay=False), default=None,
              help="旧脚本目录（递归扫 .sql/.hql/.sh/.py 与 DataX .json）")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="单个脚本文件")
@click.option("--emit-stubs", "emit_dir", type=click.Path(file_okay=False),
              default=None, help="把 SeaTunnel 目标任务的配置骨架写到该目录")
@_common
def pipe_migrate(directory, path, emit_dir, lang, fmt, output) -> None:
    """Pipeline 迁移评估 — 目标引擎、S/M/L 工作量、风险与迁移波次。"""
    from seatunnel_agent.agents.data.pipeline_migrate import (
        assess_dir,
        assess_text,
        render_markdown,
    )

    if directory:
        result = assess_dir(directory)
    elif path:
        result = assess_text(
            Path(path).name,
            Path(path).read_text(encoding="utf-8", errors="replace"))
    else:
        raise click.UsageError("提供 --dir 或 --file")
    _emit(result.to_dict(), render_markdown(result, lang=lang), fmt, output)
    if emit_dir:
        _emit_confs(emit_dir, [(j.job, j.stub)
                               for j in result.jobs if j.stub])


def register(cli) -> None:
    cli.add_command(dagopt)
    cli.add_command(rerun)
    cli.add_command(backfill_sql)
    cli.add_command(sync_strategy)
    cli.add_command(pipe_migrate)
