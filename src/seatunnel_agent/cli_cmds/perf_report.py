"""CLI entry point for the one-shot performance health report.

Discovers the suite inputs in one directory by conventional file
names (plan.txt [+ plan_before.txt], metrics.json [+ baseline.jsonl],
queries/ + stats.json, scenario.json, workload/ [+ ddl.sql]), runs
every section whose input is present, and merges one markdown/JSON
report. Skew needs the event log and stays a separate command.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from .check_runner import emit_payload as _emit
from .check_runner import report_options

_PERF_REPORT_I18N = {
    "en": {
        "title": "# Performance Health Report",
        "sec_plan": "## Execution plan (plan.txt)",
        "sec_slow": "## Slow-query diagnosis (metrics.json)",
        "sec_cost": "## Workload cost (queries/ x stats.json)",
        "sec_dag": "## Concurrency (scenario.json)",
        "sec_index": "## Index / partition advice (workload/)",
        "skipped": "Inputs not found (sections skipped):",
        "failed": "Inputs that failed to parse:",
        "hint": ("> Conventions: plan.txt [+ plan_before.txt], "
                 "metrics.json [+ baseline.jsonl], queries/ + stats.json, "
                 "scenario.json, workload/ [+ ddl.sql]. Skew needs the "
                 "event log — run skew-runtime separately."),
        "nothing": "No recognized inputs in the directory.",
    },
    "zh": {
        "title": "# 性能体检报告",
        "sec_plan": "## 执行计划（plan.txt）",
        "sec_slow": "## 慢查询诊断（metrics.json）",
        "sec_cost": "## 负载代价（queries/ × stats.json）",
        "sec_dag": "## 并发推演（scenario.json）",
        "sec_index": "## 索引分区建议（workload/）",
        "skipped": "未发现的输入（对应节跳过）：",
        "failed": "解析失败的输入：",
        "hint": ("> 约定文件名：plan.txt［+ plan_before.txt］、"
                 "metrics.json［+ baseline.jsonl］、queries/ + stats.json、"
                 "scenario.json、workload/［+ ddl.sql］。倾斜需要 event "
                 "log，请单独跑 skew-runtime。"),
        "nothing": "目录里没有可识别的输入。",
    },
}


@click.command("perf-report")
@click.option("--dir", "-d", "directory", required=True,
              type=click.Path(exists=True, file_okay=False),
              help="输入目录：按约定文件名发现各工具的输入，能跑的全跑")
@report_options
def perf_report(directory, lang, fmt, output) -> None:
    """一键体检 — 按约定文件名跑完整个性能套件，合并成一份报告。"""
    from seatunnel_agent.common.utils import normalize_lang

    lang = normalize_lang(lang)
    t = _PERF_REPORT_I18N[lang if lang in _PERF_REPORT_I18N else "zh"]
    root = Path(directory)
    sections: dict[str, Any] = {}
    skipped: list[str] = []
    failed: list[str] = []
    parts: list[str] = [t["title"], ""]

    def run_section(key: str, head: str, fn) -> None:
        try:
            result = fn()
        except ValueError as exc:
            failed.append(f"{key}: {exc}")
            return
        if result is None:
            skipped.append(key)
            return
        payload, markdown = result
        sections[key] = payload
        parts.extend([head, "", markdown, ""])

    def plan_section():
        plan = root / "plan.txt"
        if not plan.is_file():
            return None
        from seatunnel_agent.agents.data.sql_perf import (
            analyze,
            render_markdown,
        )

        result = analyze(plan.read_text(encoding="utf-8", errors="replace"))
        payload = result.to_dict()
        markdown = render_markdown(result, lang=lang)
        before = root / "plan_before.txt"
        if before.is_file():
            from seatunnel_agent.agents.data.sql_perf.diff import (
                diff_plans,
                render_diff,
            )

            delta = diff_plans(
                analyze(before.read_text(encoding="utf-8",
                                         errors="replace")), result)
            payload["diff"] = delta
            markdown += "\n\n" + render_diff(delta, lang=lang)
        return payload, markdown

    def slow_section():
        metrics = root / "metrics.json"
        if not metrics.is_file():
            return None
        from seatunnel_agent.agents.data.slow_query import (
            diagnose,
            parse_baseline,
            parse_metrics,
            render_markdown,
        )

        baseline_file = root / "baseline.jsonl"
        baseline = (baseline_file.read_text(encoding="utf-8",
                                            errors="replace")
                    if baseline_file.is_file() else "")
        diag = diagnose(parse_metrics(
            metrics.read_text(encoding="utf-8", errors="replace")),
            parse_baseline(baseline))
        return diag.to_dict(), render_markdown(diag, lang=lang)

    def cost_section():
        queries = root / "queries"
        stats_file = root / "stats.json"
        if not (queries.is_dir() and stats_file.is_file()):
            return None
        from seatunnel_agent.agents.data.sql_cost import (
            estimate_batch,
            parse_stats,
            render_batch,
        )
        from seatunnel_agent.common.utils import collect_sql_files

        stats = parse_stats(stats_file.read_text(encoding="utf-8",
                                                 errors="replace"))
        batch = estimate_batch(
            [(Path(p).name,
              Path(p).read_text(encoding="utf-8", errors="replace"))
             for p in collect_sql_files(str(queries))], stats)
        return batch, render_batch(batch, lang=lang)

    def dag_section():
        scenario = root / "scenario.json"
        if not scenario.is_file():
            return None
        from seatunnel_agent.agents.data.dag_conflict import (
            parse_scenario,
            render_markdown,
            simulate,
        )

        result = simulate(parse_scenario(
            scenario.read_text(encoding="utf-8", errors="replace")))
        return result.to_dict(), render_markdown(result, lang=lang)

    def index_section():
        workload_dir = root / "workload"
        if not workload_dir.is_dir():
            return None
        from seatunnel_agent.agents.data.index_advisor import (
            analyze_workload,
            audit,
            recommend,
            render_audit,
            render_markdown,
        )
        from seatunnel_agent.common.utils import collect_sql_files

        workload = "\n;\n".join(
            Path(p).read_text(encoding="utf-8", errors="replace")
            for p in collect_sql_files(str(workload_dir)))
        ddl_file = root / "ddl.sql"
        ddl = (ddl_file.read_text(encoding="utf-8", errors="replace")
               if ddl_file.is_file() else "")
        advice = recommend(analyze_workload(workload), ddl_text=ddl)
        payload = advice.to_dict()
        markdown = render_markdown(advice, lang=lang)
        if ddl:
            findings = audit(advice, ddl)
            payload["audit"] = findings
            markdown += "\n\n" + render_audit(findings, lang=lang)
        return payload, markdown

    run_section("plan", t["sec_plan"], plan_section)
    run_section("slow_query", t["sec_slow"], slow_section)
    run_section("cost", t["sec_cost"], cost_section)
    run_section("dag", t["sec_dag"], dag_section)
    run_section("index", t["sec_index"], index_section)

    if not sections and not failed:
        raise click.UsageError(t["nothing"] + " " + t["hint"][2:])
    if skipped:
        parts.append(t["skipped"] + " " + ", ".join(f"`{s}`"
                                                    for s in skipped))
        parts.append("")
    if failed:
        parts.append(t["failed"] + " " + ", ".join(f"`{s}`"
                                                   for s in failed))
        parts.append("")
    parts.append(t["hint"])
    _emit({"sections": sections, "skipped": skipped, "failed": failed},
          "\n".join(parts), fmt, output)

