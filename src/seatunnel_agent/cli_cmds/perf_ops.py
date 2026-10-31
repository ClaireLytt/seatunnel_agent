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

import json
from pathlib import Path

import click

from .check_runner import emit_payload as _emit
from .check_runner import fail_check, report_options, severity_gate
from .check_runner import read_input as _read
from .check_runner import track_history as _track_history


@click.command("sqlperf")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="EXPLAIN 输出文件")
@click.option("--text", type=str, default=None, help="内联 EXPLAIN 输出")
@click.option("--sql-file", "sql_path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="原 SQL 文件（配合 --llm 出改写草案）")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="按发现请求 LLM 改写 SQL（需配置 API key 与 --sql-file）")
@click.option("--fail-on-severity", "fail_severity",
              type=click.Choice(["high", "medium"]), default=None,
              help="CI gate：出现该级别及以上的发现时 exit 1")
@click.option("--before", "before_path",
              type=click.Path(exists=True, dir_okay=False), default=None,
              help="优化前的 EXPLAIN 文件（-f 为优化后，输出前后对比）")
@click.option("--fail-on-new", "fail_on_new", is_flag=True, default=False,
              help="CI gate：对比中优化后计划引入新发现时 exit 1"
                   "（需配合 --before）")
@click.option("--stats-template", "stats_template_path",
              type=click.Path(dir_okay=False), default=None,
              help="从扫描明细生成 sqlcost 统计清单骨架 JSON 写到该文件"
                   "（表名/列数已填，行数/字节/分区待补）")
@report_options
def sqlperf(path, text, sql_path, use_llm, fail_severity, before_path,
            fail_on_new, stats_template_path, lang, fmt, output) -> None:
    """执行计划分析 — EXPLAIN 文本 → join/shuffle/裁剪/下推发现与处方。"""
    from seatunnel_agent.agents.data.sql_perf import analyze, render_markdown

    if fail_on_new and not before_path:
        raise click.UsageError("--fail-on-new 需配合 --before")
    result = analyze(_read(path, text, "EXPLAIN 输出"))
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if before_path:
        from seatunnel_agent.agents.data.sql_perf.diff import diff_plans, render_diff

        before = analyze(Path(before_path).read_text(encoding="utf-8",
                                                     errors="replace"))
        delta = diff_plans(before, result)
        payload["diff"] = delta
        markdown += "\n\n" + render_diff(delta, lang=lang)
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
    if stats_template_path:
        if not result.scans:
            raise click.UsageError("计划里没有扫描节点，生成不了统计清单骨架")
        template = {"tables": [
            {"table": s.table, "rows": 0, "bytes": 0, "partitions": 0,
             "partition_col": "", "columns": s.columns}
            for s in result.scans]}
        Path(stats_template_path).write_text(
            json.dumps(template, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        click.echo(f"stats template: {len(result.scans)} table(s) -> "
                   f"{stats_template_path}（补上 rows/bytes/partitions "
                   f"即可直接喂给 sqlcost）", err=True)
    _emit(payload, markdown, fmt, output)
    if fail_on_new and payload.get("diff", {}).get("introduced"):
        introduced = payload["diff"]["introduced"]
        msg = "\n".join(f"INTRODUCED {f['code']} [{f['severity']}] "
                        f"{f['detail']}" for f in introduced)
        fail_check(msg, fmt)
    if fail_severity:
        from .check_runner import SEVERITY_RANK

        hits = [f for f in result.findings
                if SEVERITY_RANK[f.severity] >= SEVERITY_RANK[fail_severity]]
        msg = "\n".join(f"FINDING {f.code} [{f.severity}] {f.detail}"
                         for f in hits)
        problem = severity_gate(result.findings, fail_severity, msg)
        if problem:
            fail_check(problem, fmt)


@click.command("index-adv")
@click.option("--dir", "-d", "directory",
              type=click.Path(exists=True, file_okay=False), default=None,
              help="查询工作负载目录（递归 *.sql）")
@click.option("--text", type=str, default=None, help="内联多条 SQL")
@click.option("--ddl", "ddl_path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="建表 DDL 文件（可选）")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言")
@click.option("--fail-on-audit", "fail_on_audit", is_flag=True,
              default=False,
              help="CI gate：现状审计有发现（IA001–IA004）时 exit 1"
                   "（需配合 --ddl）")
@click.option("--stats", "stats_path",
              type=click.Path(exists=True, dir_okay=False), default=None,
              help="表统计清单（同 sqlcost 格式）：对每条分区建议估算"
                   "整个负载省多少扫描，按省量排序")
@report_options
def index_adv(directory, text, ddl_path, dialect, fail_on_audit, stats_path,
              lang, fmt, output) -> None:
    """索引分区推荐 — 查询频次 → 分区/分桶/组合索引与 DDL 片段。"""
    from seatunnel_agent.agents.data.index_advisor import (
        analyze_workload,
        audit,
        recommend,
        render_audit,
        render_markdown,
    )
    from seatunnel_agent.common.utils import collect_sql_files

    if fail_on_audit and not ddl_path:
        raise click.UsageError("--fail-on-audit 需配合 --ddl")
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
    payload = advice.to_dict()
    markdown = render_markdown(advice, lang=lang)
    if ddl:
        findings = audit(advice, ddl)
        payload["audit"] = findings
        markdown += "\n\n" + render_audit(findings, lang=lang)
    if stats_path:
        from seatunnel_agent.agents.data.index_advisor.roi import (
            partition_roi,
            render_roi,
        )
        from seatunnel_agent.agents.data.sql_cost import parse_stats

        stats = parse_stats(Path(stats_path).read_text(encoding="utf-8",
                                                       errors="replace"))
        payload["roi"] = partition_roi(advice, workload, stats)
        markdown += "\n\n" + render_roi(payload["roi"], lang=lang)
    _emit(payload, markdown, fmt, output)
    if fail_on_audit and payload.get("audit"):
        msg = "\n".join(f"AUDIT {f['code']} {f['table']} {f['detail']}"
                        for f in payload["audit"])
        fail_check(msg, fmt)


@click.command("sqlcost")
@click.option("--sql-file", "sql_path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="要估算的 SQL 文件")
@click.option("--dir", "-d", "directory",
              type=click.Path(exists=True, file_okay=False), default=None,
              help="批量模式：目录下所有 *.sql 对同一清单各估一次，"
                   "按核·秒排序出最贵查询榜 + 合计行")
@click.option("--file", "-f", "stats_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="表统计清单（JSON/CSV）")
@click.option("--fail-over-total-scan-gb", type=float, default=0.0,
              help="CI gate：批量合计扫描超过该 GB 数时 exit 1"
                   "（需配合 --dir）")
@click.option("--assume-partition", "assume_partitions", multiple=True,
              help="what-if：按 表:列[:分区数] 假设分区后重估一遍，"
                   "打印扫描/耗时差异（可多次）")
@click.option("--fail-over-scan-gb", type=float, default=0.0,
              help="CI gate：预估扫描超过该 GB 数时 exit 1")
@click.option("--fail-over-shuffle-gb", type=float, default=0.0,
              help="CI gate：预估 shuffle 超过该 GB 数时 exit 1")
@click.option("--compare-sql-file", "compare_sql_path",
              type=click.Path(exists=True, dir_okay=False), default=None,
              help="改写后的 SQL 文件：同清单各估一次，输出省比表")
@click.option("--fail-if-worse", "fail_if_worse", is_flag=True,
              default=False,
              help="CI gate：改写在任一维度反而更贵时 exit 1"
                   "（需配合 --compare-sql-file）")
@report_options
def sqlcost(sql_path, directory, stats_path, fail_over_total_scan_gb,
            assume_partitions, fail_over_scan_gb, fail_over_shuffle_gb,
            compare_sql_path, fail_if_worse, lang, fmt, output) -> None:
    """资源消耗预测 — SQL × 表统计 → 代价卡；可按预算挡 CI。"""
    from seatunnel_agent.agents.data.sql_cost import (
        compare,
        estimate,
        parse_assumptions,
        parse_stats,
        render_compare,
        render_markdown,
        render_what_if,
        what_if,
    )

    if fail_if_worse and not compare_sql_path:
        raise click.UsageError("--fail-if-worse 需配合 --compare-sql-file")
    if bool(sql_path) == bool(directory):
        raise click.UsageError("提供 --sql-file 或 --dir（二选一）")
    stats = parse_stats(Path(stats_path).read_text(encoding="utf-8",
                                                   errors="replace"))
    if directory:
        if assume_partitions or compare_sql_path:
            raise click.UsageError(
                "--dir 批量模式不支持 --assume-partition / --compare-sql-file")
        from seatunnel_agent.common.utils import collect_sql_files

        cards = []
        skipped = []
        for p in collect_sql_files(directory):
            try:
                cards.append((Path(p).name, estimate(
                    Path(p).read_text(encoding="utf-8", errors="replace"),
                    stats)))
            except ValueError as exc:
                skipped.append(f"{Path(p).name}: {exc}")
        if not cards:
            raise click.UsageError("目录里没有可估算的 *.sql 文件")
        cards.sort(key=lambda nc: (-nc[1].core_seconds, nc[0]))
        total_scan = sum(c.scan_bytes for _, c in cards)
        total_shuffle = sum(c.shuffle_bytes for _, c in cards)
        total_core = sum(c.core_seconds for _, c in cards)
        gb = 1 << 30
        rows = ["| query | scan_gb | shuffle_gb | core_s |",
                "| --- | --- | --- | --- |"]
        rows += [f"| {name} | {c.scan_bytes / gb:.1f} "
                 f"| {c.shuffle_bytes / gb:.1f} | {c.core_seconds:,.0f} |"
                 for name, c in cards]
        rows.append(f"| **total ({len(cards)})** | "
                    f"**{total_scan / gb:.1f}** | "
                    f"**{total_shuffle / gb:.1f}** | "
                    f"**{total_core:,.0f}** |")
        _emit({"queries": [{"name": name, **c.to_dict()}
                           for name, c in cards],
               "totals": {"scan_bytes": round(total_scan),
                          "shuffle_bytes": round(total_shuffle),
                          "core_seconds": round(total_core, 1)},
               "skipped": skipped},
              "\n".join(rows), fmt, output)
        if (fail_over_total_scan_gb
                and total_scan / gb > fail_over_total_scan_gb):
            fail_check(f"BUDGET total scan {total_scan / gb:.1f} GB > "
                       f"{fail_over_total_scan_gb:g} GB", fmt)
        return
    sql = Path(sql_path).read_text(encoding="utf-8", errors="replace")
    card = estimate(sql, stats)
    markdown = render_markdown(card, lang=lang)
    payload = card.to_dict()
    if compare_sql_path:
        rewrite_card = estimate(
            Path(compare_sql_path).read_text(encoding="utf-8",
                                             errors="replace"), stats)
        payload["compare"] = compare(card, rewrite_card)
        markdown += "\n\n" + render_compare(payload["compare"], lang=lang)
    if assume_partitions:
        try:
            assumptions = parse_assumptions(list(assume_partitions), stats)
            payload["what_if"] = what_if(card, sql, stats, assumptions)
        except ValueError as exc:
            raise click.UsageError(str(exc)) from exc
        markdown += "\n\n" + render_what_if(payload["what_if"], lang=lang)
    _emit(payload, markdown, fmt, output)
    problems: list[str] = []
    if fail_if_worse:
        worse = {axis: pct for axis, pct in
                 payload["compare"]["saved_pct"].items() if pct < 0}
        if worse:
            problems.extend(f"WORSE {axis} {-pct:g}% more expensive"
                            for axis, pct in sorted(worse.items()))
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
@click.option("--dir", "-d", "directory",
              type=click.Path(exists=True, file_okay=False), default=None,
              help="批量模式：目录下所有 *.json 逐个诊断，按回归排序出清单")
@click.option("--baseline", "baseline_path",
              type=click.Path(exists=True, dir_okay=False), default=None,
              help="历史基线 jsonl")
@click.option("--history", "history_path", type=click.Path(dir_okay=False),
              default=None,
              help="慢查询台账：主因/占比/回归倍数追加到该 jsonl")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草慢查询通报（需配置 API key）")
@click.option("--fail-over-regression", "fail_regression", type=float,
              default=0.0,
              help="CI gate：相对基线中位数的回归倍数达到该值时 exit 1"
                   "（需配合 --baseline）")
@click.option("--promote-baseline", "promote", is_flag=True, default=False,
              help="本次 run 回归低于 --promote-under 时追加进基线 jsonl，"
                   "基线自动滚动（需配合 --baseline，单 run 模式）")
@click.option("--promote-under", "promote_under", type=float, default=1.5,
              show_default=True,
              help="晋升阈值：回归倍数达到该值的 run 不进基线")
@click.option("--diff", "diff_paths", nargs=2,
              type=click.Path(exists=True, dir_okay=False), default=None,
              help="A/B 对比：两份指标 JSON（A=快跑 B=慢跑），按 stage "
                   "对齐输出差值表；与其他输入互斥")
@click.option("--trend", "trend_n", type=int, default=0,
              help="慢化趋势：台账（含本次）最近 N 次 duration 逐次上涨时"
                   "在报告点名（需配合 --history）")
@click.option("--fail-on-trend", "fail_on_trend", is_flag=True,
              default=False, help="CI gate：检出慢化趋势时 exit 1")
@report_options
def slowquery(path, text, directory, baseline_path, history_path, use_llm,
              fail_regression, promote, promote_under, diff_paths, trend_n,
              fail_on_trend, lang, fmt, output) -> None:
    """慢查询根因 — 指标 × 基线 → 排序根因与处方；--history 记台账。"""
    from seatunnel_agent.agents.data.slow_query import (
        diagnose,
        parse_baseline,
        parse_metrics,
        render_markdown,
    )

    if diff_paths:
        if path or text or directory or use_llm or promote or trend_n:
            raise click.UsageError("--diff 与其他输入/动作互斥")
        from seatunnel_agent.agents.data.slow_query import (
            diff_runs,
            render_diff,
        )

        runs = [parse_metrics(Path(p).read_text(encoding="utf-8",
                                                errors="replace"))
                for p in diff_paths]
        delta = diff_runs(runs[0], runs[1])
        _emit(delta, render_diff(delta, lang=lang), fmt, output)
        return
    baseline = (Path(baseline_path).read_text(encoding="utf-8",
                                              errors="replace")
                if baseline_path else "")
    if directory:
        if use_llm or history_path or promote:
            raise click.UsageError(
                "--dir 批量模式不支持 --llm / --history / --promote-baseline")
        diags = []
        for f in sorted(Path(directory).glob("*.json")):
            try:
                diags.append(diagnose(
                    parse_metrics(f.read_text(encoding="utf-8",
                                              errors="replace")),
                    parse_baseline(baseline)))
            except ValueError as exc:
                raise click.UsageError(f"{f.name}: {exc}") from exc
        if not diags:
            raise click.UsageError("目录里没有 *.json 指标文件")
        diags.sort(key=lambda d: (-d.regression, -d.duration_s, d.name))
        rows = ["| run | duration_s | regression | top cause |",
                "| --- | --- | --- | --- |"]
        for d in diags:
            top_code = d.causes[0].code if d.causes else "-"
            rows.append(f"| {d.name} | {d.duration_s:g} | "
                        f"{d.regression:g}x | {top_code} |")
        _emit({"runs": [d.to_dict() for d in diags]},
              "\n".join(rows), fmt, output)
        worst = diags[0]
        if fail_regression and worst.regression >= fail_regression:
            fail_check(f"REGRESSION {worst.name} {worst.regression:g}x >= "
                       f"{fail_regression:g}x", fmt)
        return
    if promote and not baseline_path:
        raise click.UsageError("--promote-baseline 需配合 --baseline")
    if (trend_n or fail_on_trend) and not history_path:
        raise click.UsageError("--trend / --fail-on-trend 需配合 --history")
    if fail_on_trend and not trend_n:
        raise click.UsageError("--fail-on-trend 需配合 --trend N")
    run = parse_metrics(_read(path, text, "执行指标"))
    diag = diagnose(run, parse_baseline(baseline))
    markdown = render_markdown(diag, lang=lang)
    payload = diag.to_dict()
    trend = None
    if trend_n:
        from seatunnel_agent.agents.data.slow_query import detect_trend
        from seatunnel_agent.agents.data.slow_query.i18n import tp as _sq_tp

        ledger = (Path(history_path).read_text(encoding="utf-8",
                                               errors="replace")
                  if Path(history_path).is_file() else "")
        entries = parse_baseline(ledger)
        entries.append({"duration_s": diag.duration_s})
        try:
            trend = detect_trend(entries, trend_n)
        except ValueError as exc:
            raise click.UsageError(str(exc)) from exc
        if trend:
            payload["trend"] = trend
            markdown += "\n\n" + _sq_tp(lang, "rpt_trend").format(
                runs=trend["runs"], from_s=f"{trend['from_s']:g}s",
                to_s=f"{trend['to_s']:g}s",
                growth_pct=f"{trend['growth_pct']:g}")
    if use_llm:
        from seatunnel_agent.agents.data.slow_query import advisor_llm
        from seatunnel_agent.agents.data.slow_query.i18n import tp

        note = advisor_llm.incident_note(diag, lang=lang)
        payload["incident_note"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_incident_note')}\n{note}\n"
    _emit(payload, markdown, fmt, output)
    if history_path:
        top = diag.causes[0] if diag.causes else None
        _track_history(history_path, {
            "duration_s": diag.duration_s,
            "regression": diag.regression,
            "causes": len(diag.causes),
            "top_share": round(top.share, 3) if top else 0.0,
        }, worse_key="duration_s")
    if promote:
        if diag.regression and diag.regression >= promote_under:
            click.echo(f"promote: skipped — regression {diag.regression:g}x "
                       f">= {promote_under:g}x", err=True)
        else:
            from datetime import datetime, timezone
            entry = {"ts": datetime.now(timezone.utc).isoformat(
                         timespec="seconds"),
                     "name": run.name, "duration_s": run.duration_s,
                     "scan_bytes": run.scan_bytes,
                     "shuffle_bytes": run.shuffle_bytes}
            with Path(baseline_path).open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            click.echo(f"promote: appended to {baseline_path}", err=True)
    if fail_regression and diag.regression >= fail_regression:
        fail_check(f"REGRESSION {diag.regression:g}x >= "
                   f"{fail_regression:g}x (baseline median "
                   f"{diag.baseline_median_s:g}s)", fmt)
    if fail_on_trend and trend:
        fail_check(f"TREND {trend['runs']} runs rising "
                   f"{trend['from_s']:g}s -> {trend['to_s']:g}s "
                   f"(+{trend['growth_pct']:g}%)", fmt)


@click.command("dagconflict")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="场景 JSON 文件")
@click.option("--text", type=str, default=None, help="内联场景 JSON")
@click.option("--fail-on-conflict", "fail_on_conflict", is_flag=True,
              default=False,
              help="CI gate：存在超容窗或写写冲突时 exit 1")
@click.option("--history", "history_path", type=click.Path(dir_okay=False),
              default=None,
              help="容量台账：峰值 slots/内存与冲突数追加到该 jsonl")
@click.option("--place", "place_dag", type=str, default=None,
              help="准入检查：对该 DAG 扫描候选起点，"
                   "选冲突最少、峰值最低的错峰位")
@click.option("--fail-if-misplaced", "fail_if_misplaced", is_flag=True,
              default=False,
              help="CI gate：声明起点劣于最优起点时 exit 1"
                   "（需配合 --place）")
@click.option("--fail-on-deadline-miss", "fail_on_deadline", is_flag=True,
              default=False,
              help="CI gate：任一声明了 deadline 的 DAG 超期时 exit 1")
@report_options
def dagconflict(path, text, fail_on_conflict, history_path, place_dag,
                fail_if_misplaced, fail_on_deadline, lang, fmt,
                output) -> None:
    """并发冲突检测 — 多 DAG 场景 → 超容窗/写写冲突/错峰建议。"""
    from seatunnel_agent.agents.data.dag_conflict import (
        parse_scenario,
        place,
        render_markdown,
        render_place,
        simulate,
    )

    if fail_if_misplaced and not place_dag:
        raise click.UsageError("--fail-if-misplaced 需配合 --place")
    scenario = parse_scenario(_read(path, text, "场景 JSON"))
    result = simulate(scenario)
    payload = result.to_dict()
    markdown = render_markdown(result, lang=lang)
    if place_dag:
        try:
            placement = place(scenario, place_dag)
        except ValueError as exc:
            raise click.UsageError(str(exc)) from exc
        payload["placement"] = placement
        markdown += "\n\n" + render_place(placement, lang=lang)
    _emit(payload, markdown, fmt, output)
    if history_path:
        _track_history(history_path, {
            "peak_slots": result.peak_slots,
            "peak_memory_gb": round(result.peak_memory_gb, 1),
            "windows": len(result.windows),
            "write_conflicts": len(result.write_conflicts),
        }, worse_key="peak_slots")
    if fail_on_conflict and (result.windows or result.write_conflicts):
        fail_check(
            f"CONFLICT windows={len(result.windows)} "
            f"write_conflicts={len(result.write_conflicts)}", fmt)
    if fail_on_deadline and result.deadline_misses:
        msg = "\n".join(
            f"DEADLINE {m['dag']} finish {m['finish']:g} > "
            f"{m['deadline']:g}" for m in result.deadline_misses)
        fail_check(msg, fmt)
    if fail_if_misplaced:
        best = payload["placement"]["best"]
        declared = payload["placement"]["declared"]
        if ((declared["windows"] + declared["write_conflicts"],
             declared["peak_slots"])
                > (best["windows"] + best["write_conflicts"],
                   best["peak_slots"])):
            fail_check(
                f"MISPLACED {place_dag} offset {declared['offset']:g} "
                f"({declared['windows']}w/{declared['write_conflicts']}c/"
                f"{declared['peak_slots']}p) vs best {best['offset']:g} "
                f"({best['windows']}w/{best['write_conflicts']}c/"
                f"{best['peak_slots']}p)", fmt)


def register(cli) -> None:
    cli.add_command(sqlperf)
    cli.add_command(index_adv)
    cli.add_command(sqlcost)
    cli.add_command(slowquery)
    cli.add_command(dagconflict)
