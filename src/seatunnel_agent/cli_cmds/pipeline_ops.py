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

from pathlib import Path

import click

from ..common.cli_common import console
from .check_runner import emit_payload as _emit
from .check_runner import fail_check
from .check_runner import track_history as _track_history


def _read(path: str | None, text: str | None, what: str) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    if text:
        return text
    raise click.UsageError(f"提供 --file 或 --text（{what}）")


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
@click.option("--base", "base_path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="基线 DAG 文件 — 额外输出变更评审")
@click.option("--fail-on-regression", is_flag=True, default=False,
              help="CI gate：关键路径变长超容忍值或引入新冗余边时 exit 1"
                   "（需配合 --base）")
@click.option("--tolerance", type=float, default=0.0, show_default=True,
              help="--fail-on-regression 允许的关键路径增幅")
@click.option("--history", "history_path", type=click.Path(dir_okay=False),
              default=None,
              help="劣化监测：本次指标追加到该 jsonl，并打印与上次的对比")
@click.option("--deadline", type=float, default=0.0,
              help="SLA 时长 — 判定是否满足并给出最小提速集合")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 写优化行动清单（需配置 API key）")
@_common
def dagopt(path, text, base_path, fail_on_regression, tolerance,
           history_path, deadline, use_llm, lang, fmt, output) -> None:
    """DAG 依赖优化 — 冗余串行边、并行批次、关键路径与加速比。"""
    from seatunnel_agent.agents.data.dag_optimize import (
        diff_dags,
        optimize,
        parse_dag,
        render_diff_markdown,
        render_markdown,
    )

    if fail_on_regression and not base_path:
        raise click.UsageError("--fail-on-regression 需配合 --base")
    graph = parse_dag(_read(path, text, "依赖图"))
    result = optimize(graph, deadline=deadline)
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    diff = None
    if base_path:
        diff = diff_dags(parse_dag(Path(base_path).read_text(
            encoding="utf-8", errors="replace")), graph, after=result)
        payload["diff"] = diff.to_dict()
        markdown = render_diff_markdown(diff, lang=lang) + "\n" + markdown
    if use_llm:
        from seatunnel_agent.agents.data.dag_optimize.advisor_llm import (
            action_plan,
        )
        from seatunnel_agent.agents.data.dag_optimize.i18n import tp

        plan = action_plan(result, lang=lang)
        payload["action_plan"] = plan
        markdown += f"\n\n### {tp(lang, 'rpt_action_plan')}\n{plan}\n"
    if history_path:
        _track_history(history_path, {
            "tasks": result.tasks, "edges": result.edges,
            "critical": result.critical_duration,
            "makespan2": result.makespans.get("2", 0.0),
            "redundant": len(result.redundant),
        }, worse_key="critical")
    _emit(payload, markdown, fmt, output)
    if fail_on_regression and diff is not None:
        problems: list[str] = []
        if diff.critical_delta > tolerance:
            problems.append(
                f"关键路径 +{diff.critical_delta:g} 超出容忍值 {tolerance:g}")
        if diff.new_redundant:
            edges = ", ".join(f"{r.up}->{r.down}" for r in diff.new_redundant)
            problems.append(f"引入新冗余边: {edges}")
        if problems:
            fail_check("\n".join(f"REGRESSION {p}" for p in problems), fmt)


@click.command("rerun")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="任务依赖图（JSON tasks/edges、DOT 或文本行）")
@click.option("--text", type=str, default=None, help="内联依赖图")
@click.option("--failed", default="", help="失败任务名，逗号分隔")
@click.option("--succeeded", default="", help="已成功任务名，逗号分隔")
@click.option("--statuses", default="",
              help='调度器状态导出（{"task":"state"} JSON 或 task=state 行）')
@click.option("--cmd", default="", help="命令模板，用 {task} 占位")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草事故通告（需配置 API key）")
@click.option("--history", "history_path", type=click.Path(dir_okay=False),
              default=None,
              help="事故台账：本次重跑的规模指标追加到该 jsonl，并与上次对比")
@_common
def rerun(path, text, failed, succeeded, statuses, use_llm, history_path,
          lang, fmt, output, cmd) -> None:
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
    markdown = render_markdown(result, lang=lang, cmd_template=cmd)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.rerun_plan.advisor_llm import (
            incident_note,
        )
        from seatunnel_agent.agents.data.rerun_plan.i18n import tp

        note = incident_note(result, lang=lang)
        payload["incident_note"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_incident_note')}\n{note}\n"
    if history_path:
        failed_n = sum(1 for t in result.tasks if t.reason == "failed")
        _track_history(history_path, {
            "failed": failed_n,
            "rerun": len(result.tasks),
            "blast_pct": round(result.blast_radius * 100, 1),
            "batches": result.batches,
            "eta": result.total_eta,
            "groups": len(result.groups),
        }, worse_key="blast_pct")
    _emit(payload, markdown, fmt, output)


@click.command("backfill-sql")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="补数规格 JSON 文件")
@click.option("--text", type=str, default=None, help="内联规格 JSON")
@click.option("--plan", type=str, default=None,
              help="补数计划器的计划 JSON — 输出逐表规格骨架（代替生成 SQL）")
@click.option("--ddl", "ddl_path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="上游 CREATE TABLE DDL 文件（配合 --llm 填充列）")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="与 --plan 连用：LLM 按 DDL 填充各规格的 source SELECT")
@_common
def backfill_sql(path, text, plan, ddl_path, use_llm, lang, fmt,
                 output) -> None:
    """回溯补数 SQL — 逐分区幂等语句与前后置校验；--plan 出规格骨架。"""
    from seatunnel_agent.agents.data.backfill_sql import (
        generate,
        parse_spec,
        render_markdown,
        specs_from_plan,
    )

    if plan:
        from seatunnel_agent.agents.data.backfill_sql.report import (
            render_specs_markdown,
        )

        specs = specs_from_plan(plan)
        warnings: list[str] = []
        if use_llm:
            from seatunnel_agent.agents.data.backfill_sql import advisor_llm

            ddl = (Path(ddl_path).read_text(encoding="utf-8",
                                            errors="replace")
                   if ddl_path else "")
            warnings = advisor_llm.fill_specs(specs, ddl, lang=lang)
        _emit({"specs": specs},
              render_specs_markdown(specs, lang=lang, warnings=warnings),
              fmt, output)
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
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 写落地推进方案（需配置 API key）")
@click.option("--fail-on-risk", "fail_risks", default="",
              help="CI gate：任一表命中这些风险码（逗号分隔，如 "
                   "latency_without_cdc）即 exit 1")
@_common
def sync_strategy(path, text, emit_dir, use_llm, fail_risks, lang, fmt,
                  output) -> None:
    """增量同步策略 — 全量/增量/CDC 推荐、风险与 SeaTunnel 配置骨架。"""
    from seatunnel_agent.agents.data.sync_strategy import (
        parse_tables,
        recommend,
        render_markdown,
    )

    result = recommend(parse_tables(_read(path, text, "表特征清单")))
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.sync_strategy.advisor_llm import (
            rollout_narrative,
        )
        from seatunnel_agent.agents.data.sync_strategy.i18n import tp

        narrative = rollout_narrative(result, lang=lang)
        payload["rollout_narrative"] = narrative
        markdown += f"\n\n### {tp(lang, 'rpt_rollout')}\n{narrative}\n"
    _emit(payload, markdown, fmt, output)
    if emit_dir:
        _emit_confs(emit_dir, [(r.table, r.config)
                               for r in result.recommendations if r.config])
    if fail_risks.strip():
        from seatunnel_agent.agents.data.sync_strategy.advisor import (
            RISK_CODES,
        )

        wanted = [c.strip() for c in fail_risks.split(",") if c.strip()]
        unknown = sorted(set(wanted) - set(RISK_CODES))
        if unknown:
            raise click.UsageError(
                f"未知风险码 {', '.join(unknown)}；可用: "
                f"{', '.join(RISK_CODES)}")
        hits = [(r.table, c) for r in result.recommendations
                for c in r.risks if c in wanted]
        if hits:
            fail_check("\n".join(f"RISK {table}: {code}"
                                 for table, code in hits), fmt)


@click.command("pipe-migrate")
@click.option("--dir", "-d", "directory",
              type=click.Path(exists=True, file_okay=False), default=None,
              help="旧脚本目录（递归扫 .sql/.hql/.sh/.py 与 DataX .json）")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="单个脚本文件")
@click.option("--emit-stubs", "emit_dir", type=click.Path(file_okay=False),
              default=None, help="把 SeaTunnel 目标任务的配置骨架写到该目录")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="对风险最大的任务额外请求 LLM 改写建议（需配置 API key）")
@click.option("--history", "history_path", type=click.Path(dir_okay=False),
              default=None,
              help="迁移燃尽：本次盘点追加到该 jsonl，并打印与上次的对比")
@_common
def pipe_migrate(directory, path, emit_dir, use_llm, history_path, lang,
                 fmt, output) -> None:
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
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.pipeline_migrate import advisor_llm

        scripts = advisor_llm.collect_scripts(
            result.jobs, root=directory,
            fallback=(result.jobs[0].job,
                      Path(path).read_text(encoding="utf-8",
                                           errors="replace"))
            if path else None)
        advice = advisor_llm.advice_for_jobs(result.jobs, scripts, lang=lang)
        payload["llm_advice"] = [{"job": j, "advice": a} for j, a in advice]
        if advice:
            markdown += "\n\n" + advisor_llm.render_advice(advice, lang)
    if history_path:
        efforts = result.effort_counts()
        counts = result.counts()
        _track_history(history_path, {
            "jobs": len(result.jobs),
            "effort_l": efforts["L"], "effort_m": efforts["M"],
            "effort_s": efforts["S"],
            "to_seatunnel": counts["seatunnel"],
            "risks": sum(len(j.risks) for j in result.jobs),
        }, worse_key="jobs")
    _emit(payload, markdown, fmt, output)
    if emit_dir:
        _emit_confs(emit_dir, [(j.job, j.stub)
                               for j in result.jobs if j.stub])


@click.command("trends")
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--last", "-n", type=int, default=0,
              help="只看最近 N 条（默认全量首尾对比）")
def trends(paths, last) -> None:
    """运维趋势汇总 — 读取 --history 产出的 jsonl，逐文件打印首尾对比。

    PATHS 为 jsonl 文件或目录（目录递归收集 *.jsonl）。
    """
    import json as _json

    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        files.extend(sorted(p.rglob("*.jsonl")) if p.is_dir() else [p])
    if not files:
        raise click.UsageError("没有找到 jsonl 趋势文件")
    for path in files:
        entries = [_json.loads(ln) for ln in
                   path.read_text(encoding="utf-8").splitlines()
                   if ln.strip()]
        if last > 0:
            entries = entries[-last:]
        if not entries:
            console.print(f"[dim]{path}: 空[/dim]")
            continue
        first, final = entries[0], entries[-1]
        span = (f"{first.get('ts', '?')} → {final.get('ts', '?')}"
                if len(entries) > 1 else first.get("ts", "?"))
        console.print(f"[bold]{path.name}[/bold]  "
                      f"{len(entries)} 条  {span}")
        for key, value in final.items():
            if key == "ts" or not isinstance(value, (int, float)):
                continue
            start = first.get(key, 0)
            mark = "" if value == start else (
                " [yellow]↑[/yellow]" if value > start else " [green]↓[/green]")
            console.print(f"  {key}: {start:g} → {value:g}{mark}")


def register(cli) -> None:
    cli.add_command(trends)
    cli.add_command(dagopt)
    cli.add_command(rerun)
    cli.add_command(backfill_sql)
    cli.add_command(sync_strategy)
    cli.add_command(pipe_migrate)
