"""质量组 CLI 命令（数据剖析/造数/关联/急救等）。

由 quality_ops.register 聚合注册;命令块按原文迁移,不改行为。
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
              help="SQL 方言 (hive/spark/mysql/postgresql/oracle/sqlserver/doris/...)")
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


@click.command("metricattr")
@click.option("--baseline", "-b", "base_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="基线结果集文件（CSV/JSONL）")
@click.option("--current", "-c", "cur_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="当前结果集文件（CSV/JSONL）")
@click.option("--dims", "-d", required=True, help="维度列（逗号分隔）")
@click.option("--metric", "-m", required=True, help="指标列")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草归因回复（需配置 API key）")
@report_options
def metricattr(base_path, cur_path, dims, metric, use_llm,
               lang, fmt, output) -> None:
    """指标异动归因 — 双结果集 × 维度 → 逐值贡献分解。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.metric_attribution import (
        attribute_change,
        render_markdown,
    )

    try:
        result = attribute_change(
            Path(base_path).read_text(encoding="utf-8", errors="replace"),
            Path(cur_path).read_text(encoding="utf-8", errors="replace"),
            dims, metric)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.metric_attribution.advisor_llm import (
            attribution_note,
        )
        from seatunnel_agent.agents.data.metric_attribution.i18n import tp

        markdown = append_llm_note(
            payload, markdown, attribution_note(result, lang=lang),
            "attribution_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


@click.command("partitionhealth")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="分区清单文件（CSV 或 JSON 列表）")
@click.option("--text", type=str, default=None, help="内联清单")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草分区通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def partitionhealth(path, text, use_llm, fail_high,
                    lang, fmt, output) -> None:
    """分区健康体检 — 清单 → 断档/空分区/倾斜/涨缩。"""
    from seatunnel_agent.agents.data.partition_health import (
        analyze_partitions,
        parse_partition_listing,
        render_markdown,
    )

    try:
        result = analyze_partitions(
            parse_partition_listing(_read(path, text, "清单")))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.partition_health.advisor_llm import (
            partition_note,
        )
        from seatunnel_agent.agents.data.partition_health.i18n import tp

        markdown = append_llm_note(
            payload, markdown, partition_note(result, lang=lang),
            "partition_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(result.findings, fmt,
                     label=lambda f: f"{f.code}:{f.table}")


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
@click.option("--grace-key", "grace_key", type=str, default="",
              help="迟到宽限的时间形键列（须是键列之一）")
@click.option("--grace", type=click.IntRange(min=0), default=0,
              help="排除宽限键最新 N 个值（窗口未闭不参与判定）")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草核对通报（需配置 API key）")
@click.option("--fail-on-diff", "fail_diff", is_flag=True, default=False,
              help="CI gate：存在缺失键或超差时 exit 1")
@report_options
def rtoffline(rt_path, off_path, keys, tolerance_pct, grace_key, grace,
              use_llm, fail_diff, lang, fmt, output) -> None:
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
            keys, tolerance_pct=tolerance_pct,
            grace_key=grace_key, grace=grace)
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
@click.option("--history", "history_path", type=click.Path(dir_okay=False),
              default=None,
              help="checkpoint 台账：最近成功 checkpoint 时长追加到该 jsonl")
@click.option("--trend", "trend_n", type=click.IntRange(min=2), default=None,
              help="爬升趋势：台账（含本次）最近 N 次时长逐次上涨时在"
                   "报告点名（需配合 --history）")
@click.option("--fail-on-trend", "fail_on_trend", is_flag=True,
              default=False, help="CI gate：检出爬升趋势时 exit 1")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草运维通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def flinkdiag(path, text, history_path, trend_n, fail_on_trend, use_llm,
              fail_high, lang, fmt, output) -> None:
    """Flink 作业诊断 — 快照 → checkpoint/背压/watermark 发现。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.data.flink_diag import (
        diagnose_job,
        parse_job_snapshot,
        render_markdown,
    )

    require_with((trend_n or fail_on_trend) and not history_path,
                 "--trend / --fail-on-trend", "--history")
    require_with(fail_on_trend and not trend_n, "--fail-on-trend",
                 "--trend N")
    try:
        snap = parse_job_snapshot(_read(path, text, "快照"))
        diag = diagnose_job(snap)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(diag, lang=lang)
    payload = diag.to_dict()
    oks = [c for c in (snap.get("checkpoints") or ())
           if isinstance(c, dict) and not c.get("failed")]
    last_ckpt_ms = float(oks[-1].get("duration_ms") or 0) if oks else None
    trend = None
    if trend_n and last_ckpt_ms is not None:
        from seatunnel_agent.agents.data.flink_diag.i18n import tp as _fd_tp

        from .check_runner import rising_trend

        ledger = (Path(history_path).read_text(encoding="utf-8",
                                               errors="replace")
                  if Path(history_path).is_file() else "")
        entries = [_json.loads(ln) for ln in ledger.splitlines()
                   if ln.strip()]
        entries.append({"last_ckpt_ms": last_ckpt_ms})
        trend = rising_trend(entries, "last_ckpt_ms", trend_n)
        if trend:
            payload["trend"] = trend
            markdown += "\n\n" + _fd_tp(lang, "rpt_trend").format(**trend)
    if use_llm:
        from seatunnel_agent.agents.data.flink_diag.advisor_llm import (
            ops_note,
        )
        from seatunnel_agent.agents.data.flink_diag.i18n import tp

        markdown = append_llm_note(
            payload, markdown, ops_note(diag, lang=lang),
            "ops_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if history_path and last_ckpt_ms is not None:
        _track_history(history_path, {
            "last_ckpt_ms": last_ckpt_ms,
            "high_findings": sum(1 for f in diag.findings
                                 if f.severity == "high")},
            worse_key="last_ckpt_ms")
    if fail_on_trend and trend:
        fail_check(f"TREND last_ckpt_ms {trend['from_v']:g} -> "
                   f"{trend['to_v']:g} over {trend['records']} runs", fmt)
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


@click.command("mockdata")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="样例 CSV（带表头）或 JSONL 文件")
@click.option("--text", type=str, default=None, help="内联样例行")
@click.option("--count", "-n", type=click.IntRange(min=1, max=10000),
              default=50, show_default=True, help="生成行数")
@click.option("--seed", type=int, default=42, show_default=True,
              help="随机种子（同样例同种子必得同结果）")
@click.option("--csv-out", "csv_out", type=click.Path(dir_okay=False),
              default=None, help="把生成的 CSV 另存到该文件")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草数据集说明（需配置 API key,只发策略不发数据）")
@report_options
def mockdata(path, text, count, seed, csv_out, use_llm,
             lang, fmt, output) -> None:
    """测试数据生成 — 真实样例 → 保形确定性 mock 行。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.mock_data import (
        generate_mock,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    try:
        headers, rows = parse_rows(_read(path, text, "样例行"))
        result = generate_mock(headers, rows, count=count, seed=seed)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    if csv_out:
        Path(csv_out).write_text(result.to_csv(), encoding="utf-8")
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.mock_data.advisor_llm import (
            dataset_note,
        )
        from seatunnel_agent.agents.data.mock_data.i18n import tp

        markdown = append_llm_note(
            payload, markdown, dataset_note(result, lang=lang),
            "dataset_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


@click.command("joinaudit")
@click.option("--left", "-l", "left_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="左表数据文件（CSV 带表头或 JSONL）")
@click.option("--right", "-r", "right_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="右表数据文件（CSV 带表头或 JSONL）")
@click.option("--keys", "-k", required=True,
              help="关联键:同名写 k,异名写 lk=rk,逗号组合多键")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草关联评审（需配置 API key,只发指标不发数据）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def joinaudit(left_path, right_path, keys, use_llm, fail_high,
              lang, fmt, output) -> None:
    """关联质量审计 — 两份数据行 + 键 → 匹配率/孤儿键/爆炸系数。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.join_audit import (
        audit_join,
        parse_keys,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    try:
        lh, lrows = parse_rows(Path(left_path).read_text(encoding="utf-8"))
        rh, rrows = parse_rows(Path(right_path).read_text(encoding="utf-8"))
        report = audit_join(lh, lrows, rh, rrows, parse_keys(keys))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(report, lang=lang)
    payload = report.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.join_audit.advisor_llm import (
            join_note,
        )
        from seatunnel_agent.agents.data.join_audit.i18n import tp

        markdown = append_llm_note(
            payload, markdown, join_note(report, lang=lang),
            "join_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(report.findings, fmt)


@click.command("dqrulegen")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="样例 CSV（带表头）或 JSONL 文件")
@click.option("--text", type=str, default=None, help="内联样例行")
@click.option("--table", "-t", required=True, help="规则要闸的表名")
@click.option("--where", type=str, default="",
              help="可选分区过滤,如 dt = '${yesterday_pt}'")
@click.option("--max-change-pct", "max_change", type=float, default=50.0,
              show_default=True, help="row_count 相对上次的变化护栏")
@click.option("--yaml-out", "yaml_out", type=click.Path(dir_okay=False),
              default=None, help="把 rules.yaml 另存到该文件")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 给出收紧建议（需配置 API key,只发检查元数据）")
@report_options
def dqrulegen(path, text, table, where, max_change, yaml_out, use_llm,
              lang, fmt, output) -> None:
    """质量规则草稿 — 表样例 → DQC 可加载的 rules.yaml。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.dq_rulegen import (
        generate_rules,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    try:
        headers, rows = parse_rows(_read(path, text, "样例行"))
        draft = generate_rules(headers, rows, table, where=where,
                               max_change_pct=max_change)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    if yaml_out:
        Path(yaml_out).write_text(draft.yaml_text, encoding="utf-8")
    markdown = render_markdown(draft, lang=lang)
    payload = draft.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.dq_rulegen.advisor_llm import (
            tighten_note,
        )
        from seatunnel_agent.agents.data.dq_rulegen.i18n import tp

        markdown = append_llm_note(
            payload, markdown, tighten_note(draft, lang=lang),
            "tighten_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


@click.command("slaboard")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="完成记录 CSV（带表头）或 JSONL 文件")
@click.option("--text", type=str, default=None, help="内联完成记录")
@click.option("--target", type=click.FloatRange(0.5, 1.0), default=0.95,
              show_default=True, help="达成率目标")
@click.option("--history", "history_path", type=click.Path(dir_okay=False),
              default=None, help="运行台账：破线数/达成率追加到该 jsonl")
@click.option("--trend", "trend_n", type=click.IntRange(min=2), default=None,
              help="恶化趋势：台账（含本次）最近 N 次 misses 逐次上涨时"
                   "在报告点名（需配合 --history）")
@click.option("--fail-on-trend", "fail_on_trend", is_flag=True,
              default=False, help="CI gate：检出恶化趋势时 exit 1")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草 SLA 通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def slaboard(path, text, target, history_path, trend_n, fail_on_trend,
             use_llm, fail_high, lang, fmt, output) -> None:
    """SLA 达成看板 — 完成记录 → 达成率/破线分级；--history 记台账。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.data.sample_profile import parse_rows
    from seatunnel_agent.agents.data.sla_board import (
        build_board,
        render_markdown,
    )

    require_with((trend_n or fail_on_trend) and not history_path,
                 "--trend / --fail-on-trend", "--history")
    require_with(fail_on_trend and not trend_n, "--fail-on-trend",
                 "--trend N")
    try:
        headers, rows = parse_rows(_read(path, text, "完成记录"))
        board = build_board(headers, rows, target=target)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(board, lang=lang)
    payload = board.to_dict()
    trend = None
    if trend_n:
        from .check_runner import rising_trend

        ledger = (Path(history_path).read_text(encoding="utf-8",
                                               errors="replace")
                  if Path(history_path).is_file() else "")
        entries = [_json.loads(ln) for ln in ledger.splitlines()
                   if ln.strip()]
        entries.append({"misses": float(board.misses_total)})
        trend = rising_trend(entries, "misses", trend_n)
        if trend:
            payload["trend"] = trend
            markdown += (f"\n\n**misses rising** — "
                         f"{trend['from_v']:g} -> {trend['to_v']:g} "
                         f"over {trend['records']} runs "
                         f"(+{trend['growth_pct']}%)")
    if use_llm:
        from seatunnel_agent.agents.data.sla_board.advisor_llm import (
            sla_note,
        )
        from seatunnel_agent.agents.data.sla_board.i18n import tp

        markdown = append_llm_note(
            payload, markdown, sla_note(board, lang=lang),
            "sla_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if history_path:
        _track_history(history_path, {
            "runs": board.runs_total,
            "misses": board.misses_total,
            "overall_rate": round(board.overall_rate, 4)}, "misses")
    if fail_on_trend and trend:
        fail_check(fmt, "misses 持续上涨 / misses rising: "
                   f"{trend['from_v']:g} -> {trend['to_v']:g}")
    if fail_high:
        fail_on_high(board.findings, fmt, label=lambda f: f.task)


@click.command("csvdoctor")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="坏 CSV 文件")
@click.option("--text", type=str, default=None, help="内联 CSV 原文")
@click.option("--csv-out", "csv_out", type=click.Path(dir_okay=False),
              default=None, help="把修复后的 CSV 另存到该文件")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草事故说明（需配置 API key,只发诊断元数据）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级诊断（列数漂移超阈/字节丢失）时 exit 1")
@report_options
def csvdoctor(path, text, csv_out, use_llm, fail_high,
              lang, fmt, output) -> None:
    """CSV 急救 — 坏文件 → 诊断 + 修复版 CSV。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.csv_doctor import (
        diagnose_csv,
        render_markdown,
    )

    try:
        report = diagnose_csv(_read(path, text, "CSV 原文"))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    if csv_out:
        Path(csv_out).write_text(report.fixed_csv, encoding="utf-8")
    markdown = render_markdown(report, lang=lang)
    payload = report.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.csv_doctor.advisor_llm import (
            incident_note,
        )
        from seatunnel_agent.agents.data.csv_doctor.i18n import tp

        markdown = append_llm_note(
            payload, markdown, incident_note(report, lang=lang),
            "incident_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(report.findings, fmt, label=lambda f: f.code)


@click.command("watermarkplan")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="观测事件 CSV（带表头）或 JSONL 文件")
@click.option("--text", type=str, default=None, help="内联事件行")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 做部署前评审（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现（时钟漂移超阈）时 exit 1")
@report_options
def watermarkplan(path, text, use_llm, fail_high,
                  lang, fmt, output) -> None:
    """水位线选型 — 观测事件 → 乱序容忍建议与 Flink 片段。"""
    from seatunnel_agent.agents.data.sample_profile import parse_rows
    from seatunnel_agent.agents.data.watermark_plan import (
        plan_watermark,
        render_markdown,
    )

    try:
        headers, rows = parse_rows(_read(path, text, "事件行"))
        plan = plan_watermark(headers, rows)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(plan, lang=lang)
    payload = plan.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.watermark_plan.advisor_llm import (
            watermark_note,
        )
        from seatunnel_agent.agents.data.watermark_plan.i18n import tp

        markdown = append_llm_note(
            payload, markdown, watermark_note(plan, lang=lang),
            "watermark_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(plan.findings, fmt, label=lambda f: f.code)


@click.command("timezoneaudit")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="数据行 CSV（带表头）或 JSONL 文件")
@click.option("--text", type=str, default=None, help="内联数据行")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草归一方案（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现（混时区/混单位）时 exit 1")
@report_options
def timezoneaudit(path, text, use_llm, fail_high,
                  lang, fmt, output) -> None:
    """时间戳体检 — 数据行 → 时区/单位/哨兵发现。"""
    from seatunnel_agent.agents.data.sample_profile import parse_rows
    from seatunnel_agent.agents.data.timezone_audit import (
        audit_timezones,
        render_markdown,
    )

    try:
        headers, rows = parse_rows(_read(path, text, "数据行"))
        audit = audit_timezones(headers, rows)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(audit, lang=lang)
    payload = audit.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.timezone_audit.advisor_llm import (
            normalization_note,
        )
        from seatunnel_agent.agents.data.timezone_audit.i18n import tp

        markdown = append_llm_note(
            payload, markdown, normalization_note(audit, lang=lang),
            "normalization_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(audit.findings, fmt, label=lambda f: f.column)


def register(cli) -> None:
    cli.add_command(sampleprofile)
    cli.add_command(distanomaly)
    cli.add_command(dupcheck)
    cli.add_command(datavolatility)
    cli.add_command(qualitytrace)
    cli.add_command(datarepair)
    cli.add_command(kafkalag)
    cli.add_command(flinkdiag)
    cli.add_command(rtlatency)
    cli.add_command(cdcdiag)
    cli.add_command(rtoffline)
    cli.add_command(partitionhealth)
    cli.add_command(metricattr)
    cli.add_command(mockdata)
    cli.add_command(joinaudit)
    cli.add_command(dqrulegen)
    cli.add_command(slaboard)
    cli.add_command(csvdoctor)
    cli.add_command(watermarkplan)
    cli.add_command(timezoneaudit)
