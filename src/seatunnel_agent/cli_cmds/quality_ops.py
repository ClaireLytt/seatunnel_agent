"""CLI entry points for the data-quality anomaly suite (36-41).

Thin wrappers over the deterministic cores, same conventions as
perf_ops.py (shared _read/_emit/fail_check):

  seatunnel-agent sampleprofile -f data.csv [--max-rows N --llm]
  seatunnel-agent distanomaly   --baseline base.csv --current cur.csv
  seatunnel-agent dupcheck      -f rows.csv [--pk id --biz-key "user,ts"]
  seatunnel-agent datavolatility -f series.csv [--fail-on-high]
  seatunnel-agent qualitytrace  -f pipeline.sql --table dws.t [--column c]
  seatunnel-agent datarepair    -f rows.csv --table dwd.t [--pk id]
  seatunnel-agent assetsearch   -f catalog.json --query "按日的订单金额"
  seatunnel-agent dictgen       -f catalog.json [--sql-file workload.sql]
  seatunnel-agent assetvalue    -f inventory.csv
  seatunnel-agent storagecost   -f inventory.csv [--partitions parts.csv]
  seatunnel-agent dbdiag        -f snapshot.json [--fail-on-high]
  seatunnel-agent grantreview   -f applications.json [--fail-on-reject]
  seatunnel-agent kafkalag      -f snapshot.json [--fail-on-high]
  seatunnel-agent flinkdiag     -f job.json [--fail-on-high]
  seatunnel-agent rtlatency     -f events.csv [--sla-ms 60000]
  seatunnel-agent cdcdiag       -f sync.json [--fail-on-high]
  seatunnel-agent rtoffline     --realtime rt.csv --offline off.csv -k dt
"""

from __future__ import annotations

import click

from .check_runner import (
    append_llm_note,
    fail_check,
    fail_on_high,
    report_options,
    require_with,
)
from .check_runner import emit_payload as _emit
from .check_runner import read_input as _read
from .check_runner import track_history as _track_history


@click.command("sampleprofile")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="CSV（带表头）或 JSONL 数据文件")
@click.option("--text", type=str, default=None, help="内联数据行")
@click.option("--max-rows", "max_rows", type=click.IntRange(min=1),
              default=2000, show_default=True,
              help="抽样上限：超过后做确定性等距抽样")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草数据体检通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def sampleprofile(path, text, max_rows, use_llm, fail_high,
                  lang, fmt, output) -> None:
    """数据抽样剖析 — CSV/JSONL → 列剖面 + 异常发现。"""
    from seatunnel_agent.agents.data.sample_profile import (
        parse_rows,
        profile_rows,
        render_markdown,
        sample_rows,
    )

    try:
        headers, rows = parse_rows(_read(path, text, "数据行"))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    result = profile_rows(headers, sample_rows(rows, max_rows),
                          total_rows=len(rows))
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.sample_profile.advisor_llm import (
            review_note,
        )
        from seatunnel_agent.agents.data.sample_profile.i18n import tp

        markdown = append_llm_note(
            payload, markdown, review_note(result, lang=lang),
            "review_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(result.findings, fmt,
                     label=lambda f: f"{f.code}:{f.column}")


@click.command("distanomaly")
@click.option("--baseline", "-b", "baseline_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="基线：CSV/JSONL 数据或 sampleprofile 的 profile JSON")
@click.option("--current", "-c", "current_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="当前：CSV/JSONL 数据或 profile JSON")
@click.option("--max-rows", "max_rows", type=click.IntRange(min=1),
              default=2000, show_default=True,
              help="剖析原始数据时每侧的抽样上限")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草漂移通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级漂移时 exit 1")
@report_options
def distanomaly(baseline_path, current_path, max_rows, use_llm, fail_high,
                lang, fmt, output) -> None:
    """数据分布异常 — 基线 vs 当前样本 → 漂移发现。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.dist_anomaly import (
        compare_profiles,
        load_profile,
        render_markdown,
    )

    def _load(path: str) -> dict:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        return load_profile(text, max_rows)

    try:
        result = compare_profiles(_load(baseline_path), _load(current_path))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.dist_anomaly.advisor_llm import (
            drift_note,
        )
        from seatunnel_agent.agents.data.dist_anomaly.i18n import tp

        markdown = append_llm_note(
            payload, markdown, drift_note(result, lang=lang),
            "drift_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(result.findings, fmt,
                     label=lambda f: f"{f.code}:{f.column}")


@click.command("dupcheck")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="CSV（带表头）或 JSONL 数据文件")
@click.option("--text", type=str, default=None, help="内联数据行")
@click.option("--pk", type=str, default="",
              help="主键列（逗号分隔），开启主键重复层")
@click.option("--biz-key", "biz_key", type=str, default="",
              help="业务键列（逗号分隔），开启业务事件重复层")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草去重处置通报（需配置 API key）")
@click.option("--fail-on-dup", "fail_dup", is_flag=True, default=False,
              help="CI gate：任何一层存在重复时 exit 1")
@report_options
def dupcheck(path, text, pk, biz_key, use_llm, fail_dup,
             lang, fmt, output) -> None:
    """数据重复检测 — 全行/主键/业务事件三层重复组。"""
    from seatunnel_agent.agents.data.dup_check import (
        detect_dups,
        render_markdown,
    )

    try:
        result = detect_dups(_read(path, text, "数据行"),
                             pk=pk or None, biz_key=biz_key or None)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.dup_check.advisor_llm import (
            dedup_note,
        )
        from seatunnel_agent.agents.data.dup_check.i18n import tp

        markdown = append_llm_note(
            payload, markdown, dedup_note(result, lang=lang),
            "dedup_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_dup:
        extra = result.row_dup_rows + result.pk_dup_rows + result.biz_dup_rows
        if extra:
            fail_check(f"DUPLICATES {extra} extra row(s)", fmt)


@click.command("datavolatility")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="序列文件：date,metric,value 的 CSV/JSONL")
@click.option("--text", type=str, default=None, help="内联序列行")
@click.option("--period", type=click.IntRange(min=1), default=7,
              show_default=True, help="同比对比的周期点数")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草波动通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级波动时 exit 1")
@report_options
def datavolatility(path, text, period, use_llm, fail_high,
                   lang, fmt, output) -> None:
    """数据波动分析 — 时间序列 → 突增/突降/位移/走平/断档。"""
    from seatunnel_agent.agents.data.data_volatility import (
        analyze_series,
        parse_series,
        render_markdown,
    )

    try:
        result = analyze_series(parse_series(_read(path, text, "序列行")),
                                 period=period)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.data_volatility.advisor_llm import (
            volatility_note,
        )
        from seatunnel_agent.agents.data.data_volatility.i18n import tp

        markdown = append_llm_note(
            payload, markdown, volatility_note(result, lang=lang),
            "volatility_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(result.findings, fmt,
                     label=lambda f: f"{f.code}:{f.metric}")


@click.command("qualitytrace")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="流水线 SQL 脚本文件")
@click.option("--text", type=str, default=None, help="内联 SQL 脚本")
@click.option("--table", "-t", required=True, help="出问题的表")
@click.option("--column", "-c", default="", help="出问题的列（可选）")
@click.option("--symptom", default="", help="一句话症状（可选）")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草追踪通报（需配置 API key）")
@report_options
def qualitytrace(path, text, table, column, symptom, dialect, use_llm,
                 lang, fmt, output) -> None:
    """质量根因追踪 — 事件 × SQL 血缘 → 嫌疑排行 + 验证 SQL。"""
    from seatunnel_agent.agents.data.quality_trace import (
        build_graph_from_sql,
        render_markdown,
        trace_quality,
    )

    try:
        graph, warnings = build_graph_from_sql(
            _read(path, text, "SQL 脚本"), dialect=dialect)
        result = trace_quality(graph, warnings, table,
                               column=column, symptom=symptom)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.quality_trace.advisor_llm import (
            trace_note,
        )
        from seatunnel_agent.agents.data.quality_trace.i18n import tp

        markdown = append_llm_note(
            payload, markdown, trace_note(result, lang=lang),
            "trace_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


@click.command("datarepair")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="CSV（带表头）或 JSONL 数据文件")
@click.option("--text", type=str, default=None, help="内联数据行")
@click.option("--table", "-t", default="<table>", show_default=True,
              help="修复 SQL 里的目标表名")
@click.option("--pk", type=str, default="",
              help="主键列（逗号分隔），开启主键去重动作")
@click.option("--biz-key", "biz_key", type=str, default="",
              help="业务键列（逗号分隔），开启业务键去重动作")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草修复变更说明（需配置 API key）")
@report_options
def datarepair(path, text, table, pk, biz_key, use_llm,
               lang, fmt, output) -> None:
    """一致性修复 — 数据行 → 修复 SQL 模板清单。"""
    from seatunnel_agent.agents.data.data_repair import (
        plan_repairs,
        render_markdown,
    )

    try:
        plan = plan_repairs(_read(path, text, "数据行"), table=table,
                            pk=pk or None, biz_key=biz_key or None)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(plan, lang=lang)
    payload = plan.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.data_repair.advisor_llm import (
            repair_note,
        )
        from seatunnel_agent.agents.data.data_repair.i18n import tp

        markdown = append_llm_note(
            payload, markdown, repair_note(plan, lang=lang),
            "repair_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


@click.command("assetsearch")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="资产目录：JSON 清单或建表 DDL 文件")
@click.option("--text", type=str, default=None, help="内联目录")
@click.option("--query", "-q", required=True, help="自然语言业务需求")
@click.option("--limit", type=click.IntRange(min=1), default=10,
              show_default=True, help="返回命中数上限")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草选表推荐（需配置 API key）")
@report_options
def assetsearch(path, text, query, limit, use_llm, lang, fmt, output) -> None:
    """数据资产搜索 — 目录 × 自然语言 → 可解释命中排行。"""
    from seatunnel_agent.agents.data.asset_search import (
        parse_catalog,
        render_markdown,
        search_assets,
    )

    try:
        result = search_assets(parse_catalog(_read(path, text, "资产目录")),
                               query, limit=limit)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.asset_search.advisor_llm import (
            recommend_note,
        )
        from seatunnel_agent.agents.data.asset_search.i18n import tp

        markdown = append_llm_note(
            payload, markdown, recommend_note(result, lang=lang),
            "recommendation", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


def register(cli) -> None:
    cli.add_command(sampleprofile)
    cli.add_command(distanomaly)
    cli.add_command(dupcheck)
    cli.add_command(datavolatility)
    cli.add_command(qualitytrace)
    cli.add_command(datarepair)
    cli.add_command(assetsearch)
    cli.add_command(datadict)
    cli.add_command(assetvalue)
    cli.add_command(storagecost)
    cli.add_command(dbdiag)
    cli.add_command(grantreview)
    cli.add_command(kafkalag)
    cli.add_command(flinkdiag)
    cli.add_command(rtlatency)
    cli.add_command(cdcdiag)
    cli.add_command(rtoffline)


@click.command("rtoffline")
@click.option("--realtime", "-r", "rt_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="实时结果集文件（CSV/JSONL）")
@click.option("--offline", "off_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="离线结果集文件（CSV/JSONL）")
@click.option("--keys", "-k", required=True, help="键列（逗号分隔）")
@click.option("--tolerance", "tolerance_pct", type=float, default=1.0,
              show_default=True, help="相对容差（%）")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草核对通报（需配置 API key）")
@click.option("--fail-on-diff", "fail_diff", is_flag=True, default=False,
              help="CI gate：存在缺失键或超差时 exit 1")
@report_options
def rtoffline(rt_path, off_path, keys, tolerance_pct, use_llm, fail_diff,
              lang, fmt, output) -> None:
    """实时离线核对 — 双结果集 × 键 × 容差 → 差异 + 偏差判定。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.rt_offline_diff import (
        compare_results,
        render_markdown,
    )

    try:
        result = compare_results(
            Path(rt_path).read_text(encoding="utf-8", errors="replace"),
            Path(off_path).read_text(encoding="utf-8", errors="replace"),
            keys, tolerance_pct=tolerance_pct)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.rt_offline_diff.advisor_llm import (
            recon_note,
        )
        from seatunnel_agent.agents.data.rt_offline_diff.i18n import tp

        markdown = append_llm_note(
            payload, markdown, recon_note(result, lang=lang),
            "recon_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_diff:
        issues = (len(result.missing_in_rt) + len(result.missing_in_off)
                  + len(result.mismatches))
        if issues:
            fail_check(f"DIFF {issues} issue(s)", fmt)


@click.command("cdcdiag")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="同步快照 JSON 文件")
@click.option("--text", type=str, default=None, help="内联快照 JSON")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草事故通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def cdcdiag(path, text, use_llm, fail_high, lang, fmt, output) -> None:
    """CDC 同步异常诊断 — 快照 → binlog/断点/丢数风险发现。"""
    from seatunnel_agent.agents.data.cdc_diag import (
        diagnose_cdc,
        parse_cdc_snapshot,
        render_markdown,
    )

    try:
        diag = diagnose_cdc(parse_cdc_snapshot(_read(path, text, "快照")))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(diag, lang=lang)
    payload = diag.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.cdc_diag.advisor_llm import (
            incident_note,
        )
        from seatunnel_agent.agents.data.cdc_diag.i18n import tp

        markdown = append_llm_note(
            payload, markdown, incident_note(diag, lang=lang),
            "incident_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(diag.findings, fmt)


@click.command("rtlatency")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="事件时间戳行文件（CSV 或 JSONL）")
@click.option("--text", type=str, default=None, help="内联事件行")
@click.option("--sla-ms", "sla_ms", type=float, default=0.0,
              help="端到端 SLA（毫秒，0 为不检）")
@click.option("--fail-on-breach", "fail_breach", is_flag=True, default=False,
              help="CI gate：存在 SLA 破线事件时 exit 1（需配合 --sla-ms）")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草延迟通报（需配置 API key）")
@report_options
def rtlatency(path, text, sla_ms, fail_breach, use_llm,
              lang, fmt, output) -> None:
    """实时延迟分析 — 事件时间戳 → 分段分位 + 离群事件。"""
    from seatunnel_agent.agents.data.rt_latency import (
        analyze_latency,
        parse_events,
        render_markdown,
    )

    require_with(fail_breach and not sla_ms, "--fail-on-breach", "--sla-ms")
    try:
        stages, events = parse_events(_read(path, text, "事件行"))
        result = analyze_latency(stages, events, sla_ms=sla_ms)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.rt_latency.advisor_llm import (
            latency_note,
        )
        from seatunnel_agent.agents.data.rt_latency.i18n import tp

        markdown = append_llm_note(
            payload, markdown, latency_note(result, lang=lang),
            "latency_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_breach and result.breaches:
        fail_check(f"SLA {result.breaches} breach(es) over "
                   f"{sla_ms:g}ms", fmt)


@click.command("flinkdiag")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="作业快照 JSON 文件")
@click.option("--text", type=str, default=None, help="内联快照 JSON")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草运维通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def flinkdiag(path, text, use_llm, fail_high, lang, fmt, output) -> None:
    """Flink 作业诊断 — 快照 → checkpoint/背压/watermark 发现。"""
    from seatunnel_agent.agents.data.flink_diag import (
        diagnose_job,
        parse_job_snapshot,
        render_markdown,
    )

    try:
        diag = diagnose_job(parse_job_snapshot(_read(path, text, "快照")))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(diag, lang=lang)
    payload = diag.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.flink_diag.advisor_llm import (
            ops_note,
        )
        from seatunnel_agent.agents.data.flink_diag.i18n import tp

        markdown = append_llm_note(
            payload, markdown, ops_note(diag, lang=lang),
            "ops_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(diag.findings, fmt)


@click.command("kafkalag")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="消费组快照文件（JSON 或 CSV）")
@click.option("--text", type=str, default=None, help="内联快照")
@click.option("--history", "history_path", type=click.Path(dir_okay=False),
              default=None,
              help="积压台账：group/total_lag 追加到该 jsonl 并打印漂移")
@click.option("--trend", "trend_n", type=click.IntRange(min=2), default=None,
              help="持续增长：台账（含本次）最近 N 次 total_lag 逐次上涨"
                   "时在报告点名（需配合 --history）")
@click.option("--fail-on-trend", "fail_on_trend", is_flag=True,
              default=False, help="CI gate：检出持续增长时 exit 1")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草运维通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def kafkalag(path, text, history_path, trend_n, fail_on_trend, use_llm,
             fail_high, lang, fmt, output) -> None:
    """Kafka 消费积压诊断 — 快照 → 发现 + 追赶 ETA；--history 记台账。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.data.kafka_lag import (
        analyze_lag,
        lag_trend,
        parse_lag_snapshot,
        render_markdown,
    )

    require_with((trend_n or fail_on_trend) and not history_path,
                 "--trend / --fail-on-trend", "--history")
    require_with(fail_on_trend and not trend_n, "--fail-on-trend",
                 "--trend N")
    try:
        group, parts = parse_lag_snapshot(_read(path, text, "快照"))
        result = analyze_lag(group, parts)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    trend = None
    if trend_n:
        from seatunnel_agent.agents.data.kafka_lag.i18n import tp as _kl_tp

        ledger = (Path(history_path).read_text(encoding="utf-8",
                                               errors="replace")
                  if Path(history_path).is_file() else "")
        entries = [_json.loads(ln) for ln in ledger.splitlines()
                   if ln.strip()]
        entries.append({"total_lag": result.total_lag})
        trend = lag_trend(entries, trend_n)
        if trend:
            payload["trend"] = trend
            markdown += "\n\n" + _kl_tp(lang, "rpt_trend").format(**trend)
    if use_llm:
        from seatunnel_agent.agents.data.kafka_lag.advisor_llm import (
            ops_note,
        )
        from seatunnel_agent.agents.data.kafka_lag.i18n import tp

        markdown = append_llm_note(
            payload, markdown, ops_note(result, lang=lang),
            "ops_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if history_path:
        _track_history(history_path, {
            "total_lag": result.total_lag,
            "partitions": len(result.partitions),
            "high_findings": sum(1 for f in result.findings
                                 if f.severity == "high")},
            worse_key="total_lag")
    if fail_on_trend and trend:
        fail_check(f"TREND total_lag {trend['from_lag']} -> "
                   f"{trend['to_lag']} over {trend['snapshots']} "
                   f"snapshots", fmt)
    if fail_high:
        fail_on_high(result.findings, fmt)


@click.command("grantreview")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="申请单 JSON 文件（单份或列表）")
@click.option("--text", type=str, default=None, help="内联申请单 JSON")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草逐份回复（需配置 API key）")
@click.option("--fail-on-reject", "fail_reject", is_flag=True, default=False,
              help="CI gate：存在拒绝结论时 exit 1")
@report_options
def grantreview(path, text, use_llm, fail_reject, lang, fmt, output) -> None:
    """权限申请审核 — 申请单 → 风险分 + 批准/降级/拒绝。"""
    from seatunnel_agent.agents.data.grant_review import (
        parse_applications,
        render_markdown,
        review_grants,
    )

    try:
        result = review_grants(parse_applications(_read(path, text, "申请单")))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.grant_review.advisor_llm import (
            review_note,
        )
        from seatunnel_agent.agents.data.grant_review.i18n import tp

        markdown = append_llm_note(
            payload, markdown, review_note(result, lang=lang),
            "replies", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_reject:
        rejected = [r.applicant for r in result.reviews
                    if r.decision == "reject"]
        if rejected:
            fail_check("REJECT " + ", ".join(rejected), fmt)


@click.command("dbdiag")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="状态快照 JSON 文件")
@click.option("--text", type=str, default=None, help="内联快照 JSON")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草事故通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def dbdiag(path, text, use_llm, fail_high, lang, fmt, output) -> None:
    """数据库运行诊断 — 快照 → 发现 + 处方。"""
    from seatunnel_agent.agents.data.db_diag import (
        diagnose_snapshot,
        parse_snapshot,
        render_markdown,
    )

    try:
        diag = diagnose_snapshot(parse_snapshot(_read(path, text, "快照")))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(diag, lang=lang)
    payload = diag.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.db_diag.advisor_llm import (
            incident_note,
        )
        from seatunnel_agent.agents.data.db_diag.i18n import tp

        markdown = append_llm_note(
            payload, markdown, incident_note(diag, lang=lang),
            "incident_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(diag.findings, fmt)


@click.command("storagecost")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="资产清单：CSV 或 JSON 文件(可含 avg_file_mb)")
@click.option("--text", type=str, default=None, help="内联清单行")
@click.option("--partitions", "parts_path",
              type=click.Path(exists=True, dir_okay=False), default=None,
              help="可选分区明细：table,partition,size_gb")
@click.option("--retention-days", "retention", type=click.IntRange(min=1),
              default=365, show_default=True, help="分区保留天数")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草治理通报（需配置 API key）")
@report_options
def storagecost(path, text, parts_path, retention, use_llm,
                lang, fmt, output) -> None:
    """存储成本治理 — 清单 ± 分区 → 迁冷/清理/合并动作。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.storage_cost import (
        render_markdown,
        run_storage_analysis,
    )

    parts = (Path(parts_path).read_text(encoding="utf-8", errors="replace")
             if parts_path else "")
    try:
        result = run_storage_analysis(_read(path, text, "资产清单"),
                                      partitions_text=parts,
                                      retention_days=retention)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.storage_cost.advisor_llm import (
            governance_note,
        )
        from seatunnel_agent.agents.data.storage_cost.i18n import tp

        markdown = append_llm_note(
            payload, markdown, governance_note(result, lang=lang),
            "governance_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


@click.command("assetvalue")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="资产清单：CSV 或 JSON 文件")
@click.option("--text", type=str, default=None, help="内联清单行")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草评估通报（需配置 API key）")
@report_options
def assetvalue(path, text, use_llm, lang, fmt, output) -> None:
    """资产价值评估 — 清单 → 分层 + 价值×成本象限。"""
    from seatunnel_agent.agents.data.asset_value import (
        parse_inventory,
        render_markdown,
        value_assets,
    )

    try:
        result = value_assets(parse_inventory(_read(path, text, "资产清单")))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.asset_value.advisor_llm import (
            grading_note,
        )
        from seatunnel_agent.agents.data.asset_value.i18n import tp

        markdown = append_llm_note(
            payload, markdown, grading_note(result, lang=lang),
            "grading_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


@click.command("dictgen")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="资产目录：JSON 清单或建表 DDL 文件")
@click.option("--text", type=str, default=None, help="内联目录")
@click.option("--sql-file", "sql_path",
              type=click.Path(exists=True, dir_okay=False), default=None,
              help="可选 SQL 负载文件（统计使用频次）")
@click.option("--min-coverage", "min_cov", type=float, default=0.0,
              help="CI gate：平均注释覆盖率低于该值时 exit 1")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 草拟缺失的业务描述（需配置 API key）")
@report_options
def datadict(path, text, sql_path, min_cov, use_llm,
             lang, fmt, output) -> None:
    """数据字典生成 — 目录 ± SQL 负载 → 角色/频次/覆盖率骨架。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.data_dict import (
        generate_dict,
        render_markdown,
    )

    sql = (Path(sql_path).read_text(encoding="utf-8", errors="replace")
           if sql_path else "")
    try:
        result = generate_dict(_read(path, text, "资产目录"), sql_text=sql)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.data_dict.advisor_llm import (
            describe_columns,
        )
        from seatunnel_agent.agents.data.data_dict.i18n import tp

        markdown = append_llm_note(
            payload, markdown, describe_columns(result, lang=lang),
            "descriptions", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if min_cov:
        avg = (sum(t.comment_coverage for t in result.tables)
               / len(result.tables)) if result.tables else 0.0
        if avg < min_cov:
            fail_check(f"COVERAGE {avg:.0f}% < {min_cov:g}%", fmt)
