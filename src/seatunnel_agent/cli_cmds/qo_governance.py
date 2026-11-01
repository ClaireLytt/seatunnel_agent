"""治理组 CLI 命令（资产/契约/成本/下线/覆盖等）。

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


@click.command("capacityforecast")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="存储序列文件：date,metric,value 的 CSV/JSONL")
@click.option("--text", type=str, default=None, help="内联序列行")
@click.option("--quota", type=float, required=True,
              help="容量配额（与数值同单位，GB 或行数）")
@click.option("--window", type=click.IntRange(min=2), default=14,
              show_default=True, help="斜率窗口点数")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草容量通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级告警（30 天内耗尽）时 exit 1")
@report_options
def capacityforecast(path, text, quota, window, use_llm, fail_high,
                     lang, fmt, output) -> None:
    """容量耗尽预测 — 序列 × 配额 → 耗尽日期 + 增长大户。"""
    from seatunnel_agent.agents.data.capacity_forecast import (
        forecast_capacity,
        render_markdown,
    )

    try:
        result = forecast_capacity(_read(path, text, "序列行"),
                                   quota=quota, window=window)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.capacity_forecast.advisor_llm import (
            capacity_note,
        )
        from seatunnel_agent.agents.data.capacity_forecast.i18n import tp

        markdown = append_llm_note(
            payload, markdown, capacity_note(result, lang=lang),
            "capacity_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(result.findings, fmt)


@click.command("layercheck")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="流水线 SQL 脚本文件")
@click.option("--text", type=str, default=None, help="内联 SQL 脚本")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/postgresql/oracle/sqlserver/doris/...)")
@click.option("--layers", "layers_path",
              type=click.Path(exists=True, dir_okay=False), default=None,
              help="自定义分层表 JSON 文件（{前缀: 层级}，替换内置）")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草整改通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级违规时 exit 1")
@report_options
def layercheck(path, text, dialect, layers_path, use_llm, fail_high,
               lang, fmt, output) -> None:
    """数仓分层体检 — SQL 血缘 → 分层违规 + 处方。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.layer_check import (
        parse_layer_map,
        render_markdown,
        run_layer_check,
    )

    try:
        layers = (parse_layer_map(Path(layers_path).read_text(
            encoding="utf-8", errors="replace")) if layers_path else None)
        result = run_layer_check(_read(path, text, "SQL 脚本"),
                                 dialect=dialect, layers=layers)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.layer_check.advisor_llm import (
            layering_note,
        )
        from seatunnel_agent.agents.data.layer_check.i18n import tp

        markdown = append_llm_note(
            payload, markdown, layering_note(result, lang=lang),
            "layering_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(result.findings, fmt,
                     label=lambda f: f"{f.code}:{f.detail.get('dst', '?')}")


@click.command("grantreview")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="申请单 JSON 文件（单份或列表）")
@click.option("--text", type=str, default=None, help="内联申请单 JSON")
@click.option("--vocabulary", "vocab_path",
              type=click.Path(exists=True, dir_okay=False), default=None,
              help="自定义敏感词表 JSON 文件（{s3: [...], s2: [...]}，"
                   "按级替换内置词表）")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草逐份回复（需配置 API key）")
@click.option("--fail-on-reject", "fail_reject", is_flag=True, default=False,
              help="CI gate：存在拒绝结论时 exit 1")
@report_options
def grantreview(path, text, vocab_path, use_llm, fail_reject,
                lang, fmt, output) -> None:
    """权限申请审核 — 申请单 → 风险分 + 批准/降级/拒绝。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.grant_review import (
        parse_applications,
        parse_vocabulary,
        render_markdown,
        review_grants,
    )

    try:
        vocab = (parse_vocabulary(Path(vocab_path).read_text(
            encoding="utf-8", errors="replace")) if vocab_path else None)
        result = review_grants(parse_applications(_read(path, text, "申请单")),
                               vocab=vocab)
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
@click.option("--history", "history_path", type=click.Path(dir_okay=False),
              default=None,
              help="运行台账：连接数/执行线程/高危数追加到该 jsonl")
@click.option("--trend", "trend_n", type=click.IntRange(min=2), default=None,
              help="爬升趋势：台账（含本次）最近 N 次 threads_connected "
                   "逐次上涨时在报告点名（需配合 --history）")
@click.option("--fail-on-trend", "fail_on_trend", is_flag=True,
              default=False, help="CI gate：检出爬升趋势时 exit 1")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草事故通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def dbdiag(path, text, history_path, trend_n, fail_on_trend, use_llm,
           fail_high, lang, fmt, output) -> None:
    """数据库运行诊断 — 快照 → 发现 + 处方；--history 记台账。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.data.db_diag import (
        diagnose_snapshot,
        parse_snapshot,
        render_markdown,
    )

    require_with((trend_n or fail_on_trend) and not history_path,
                 "--trend / --fail-on-trend", "--history")
    require_with(fail_on_trend and not trend_n, "--fail-on-trend",
                 "--trend N")
    try:
        snap = parse_snapshot(_read(path, text, "快照"))
        diag = diagnose_snapshot(snap)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(diag, lang=lang)
    payload = diag.to_dict()
    status = snap.get("status") or {}
    connected = float(status.get("threads_connected") or 0)
    trend = None
    if trend_n:
        from .check_runner import rising_trend

        ledger = (Path(history_path).read_text(encoding="utf-8",
                                               errors="replace")
                  if Path(history_path).is_file() else "")
        entries = [_json.loads(ln) for ln in ledger.splitlines()
                   if ln.strip()]
        entries.append({"threads_connected": connected})
        trend = rising_trend(entries, "threads_connected", trend_n)
        if trend:
            payload["trend"] = trend
            markdown += (f"\n\n**threads_connected rising** — "
                         f"{trend['from_v']:g} -> {trend['to_v']:g} "
                         f"over {trend['records']} snapshots "
                         f"(+{trend['growth_pct']}%)")
    if use_llm:
        from seatunnel_agent.agents.data.db_diag.advisor_llm import (
            incident_note,
        )
        from seatunnel_agent.agents.data.db_diag.i18n import tp

        markdown = append_llm_note(
            payload, markdown, incident_note(diag, lang=lang),
            "incident_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if history_path:
        _track_history(history_path, {
            "threads_connected": connected,
            "threads_running": float(status.get("threads_running") or 0),
            "high_findings": sum(1 for f in diag.findings
                                 if f.severity == "high")},
            worse_key="high_findings")
    if fail_on_trend and trend:
        fail_check(f"TREND threads_connected {trend['from_v']:g} -> "
                   f"{trend['to_v']:g} over {trend['records']} "
                   f"snapshots", fmt)
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


@click.command("contractgen")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="CREATE TABLE DDL 文件")
@click.option("--text", type=str, default=None, help="内联 DDL")
@click.option("--tables", "-t", type=str, default="",
              help="限定表（逗号分隔,默认全部）")
@click.option("--no-types", "no_types", is_flag=True, default=False,
              help="不固定列类型")
@click.option("--threshold", type=click.FloatRange(0.0, 1.0), default=0.8,
              show_default=True,
              help="注释覆盖率达标线:达标即 require_comments")
@click.option("--strict", is_flag=True, default=False,
              help="allow_extra_columns: false（结构冻结）")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/postgresql/oracle/sqlserver/doris/...)")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 给出收紧建议（需配置 API key）")
@report_options
def contractgen(path, text, tables, no_types, threshold, strict, dialect,
                use_llm, lang, fmt, output) -> None:
    """契约草稿生成 — DDL → 契约体检可消费的 contract YAML。"""
    from seatunnel_agent.agents.data.contract_gen import (
        generate_contract,
        render_markdown,
    )

    wanted = [t.strip() for t in tables.split(",") if t.strip()]
    try:
        draft = generate_contract(_read(path, text, "DDL"), dialect=dialect,
                                  with_types=not no_types,
                                  comment_threshold=threshold,
                                  allow_extra=not strict,
                                  tables=wanted or None)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(draft, lang=lang)
    payload = draft.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.contract_gen.advisor_llm import (
            tighten_note,
        )
        from seatunnel_agent.agents.data.contract_gen.i18n import tp

        markdown = append_llm_note(
            payload, markdown, tighten_note(draft, lang=lang),
            "tighten_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


@click.command("modelreview")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="CREATE TABLE DDL 文件")
@click.option("--text", type=str, default=None, help="内联 DDL")
@click.option("--wide-limit", "wide_limit", type=click.IntRange(min=1),
              default=50, show_default=True, help="宽表阈值（列数）")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/postgresql/oracle/sqlserver/doris/...)")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 给出改造建议（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def modelreview(path, text, wide_limit, dialect, use_llm, fail_high,
                lang, fmt, output) -> None:
    """建模体检 — 数仓 DDL → 星型结构分级发现。"""
    from seatunnel_agent.agents.data.model_review import (
        render_markdown,
        review_model,
    )

    try:
        report = review_model(_read(path, text, "DDL"), dialect=dialect,
                              wide_limit=wide_limit)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(report, lang=lang)
    payload = report.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.model_review.advisor_llm import (
            modeling_note,
        )
        from seatunnel_agent.agents.data.model_review.i18n import tp

        markdown = append_llm_note(
            payload, markdown, modeling_note(report, lang=lang),
            "modeling_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(report.findings, fmt)


@click.command("duppipeline")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="流水线 SQL 脚本文件")
@click.option("--text", type=str, default=None, help="内联 SQL 脚本")
@click.option("--fanout", type=click.IntRange(min=2), default=3,
              show_default=True, help="源表直读目标数达到该值记 DP003")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/postgresql/oracle/sqlserver/doris/...)")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草收敛方案（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def duppipeline(path, text, fanout, dialect, use_llm, fail_high,
                lang, fmt, output) -> None:
    """重复建设检测 — 流水线 SQL → 同源双建分级发现。"""
    from seatunnel_agent.agents.data.dup_pipeline import (
        detect_dup_pipelines,
        render_markdown,
    )

    try:
        report = detect_dup_pipelines(_read(path, text, "SQL 脚本"),
                                      dialect=dialect, fanout=fanout)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(report, lang=lang)
    payload = report.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.dup_pipeline.advisor_llm import (
            consolidation_note,
        )
        from seatunnel_agent.agents.data.dup_pipeline.i18n import tp

        markdown = append_llm_note(
            payload, markdown, consolidation_note(report, lang=lang),
            "consolidation_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(report.findings, fmt)


@click.command("maskpreview")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="CSV（带表头）或 JSONL 数据文件")
@click.option("--text", type=str, default=None, help="内联数据行")
@click.option("--preview-rows", "preview_rows", type=click.IntRange(min=1),
              default=20, show_default=True, help="脱敏样例行数")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草脱敏策略说明（需配置 API key,只发规则元数据不发数据）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：检出 high 级敏感列时 exit 1")
@report_options
def maskpreview(path, text, preview_rows, use_llm, fail_high,
                lang, fmt, output) -> None:
    """脱敏预览 — 数据行 → 敏感列判定 + 保格式脱敏样例。"""
    from seatunnel_agent.agents.data.mask_preview import (
        preview_mask,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    try:
        headers, rows = parse_rows(_read(path, text, "数据行"))
        preview = preview_mask(headers, rows, preview_rows=preview_rows)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(preview, lang=lang)
    payload = preview.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.mask_preview.advisor_llm import (
            policy_note,
        )
        from seatunnel_agent.agents.data.mask_preview.i18n import tp

        markdown = append_llm_note(
            payload, markdown, policy_note(preview, lang=lang),
            "policy_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(preview.columns, fmt, label=lambda c: c.name)


@click.command("fieldusage")
@click.option("--ddl", "ddl_path", type=click.Path(exists=True, dir_okay=False),
              required=True, help="CREATE TABLE DDL 文件")
@click.option("--queries", "-q", "queries_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="查询负载 SQL 文件")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/postgresql/oracle/sqlserver/doris/...)")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 给出处置建议（需配置 API key）")
@click.option("--fail-on-unused", "fail_unused", is_flag=True,
              default=False, help="CI gate：存在从未被读的表时 exit 1")
@report_options
def fieldusage(ddl_path, queries_path, dialect, use_llm, fail_unused,
               lang, fmt, output) -> None:
    """字段使用率盘点 — DDL + 查询负载 → 列级引用计数。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.field_usage import (
        analyze_usage,
        render_markdown,
    )

    try:
        report = analyze_usage(
            Path(ddl_path).read_text(encoding="utf-8"),
            Path(queries_path).read_text(encoding="utf-8"),
            dialect=dialect)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(report, lang=lang)
    payload = report.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.field_usage.advisor_llm import (
            usage_note,
        )
        from seatunnel_agent.agents.data.field_usage.i18n import tp

        markdown = append_llm_note(
            payload, markdown, usage_note(report, lang=lang),
            "usage_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_unused:
        dead = [f.table for f in report.findings if f.code == "FU001"]
        if dead:
            fail_check(fmt, "存在无人读的表 / unread tables: "
                       + ", ".join(dead))


@click.command("offboardplan")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="流水线 SQL 脚本文件")
@click.option("--text", type=str, default=None, help="内联 SQL 脚本")
@click.option("--table", "-t", required=True, help="要下线的表")
@click.option("--grace-days", "grace_days", type=click.IntRange(min=0),
              default=30, show_default=True, help="公示期（天）")
@click.option("--archive-db", "archive_db", default="archive",
              show_default=True, help="归档库名")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草下线通告（需配置 API key）")
@click.option("--fail-on-blocked", "fail_blocked", is_flag=True,
              default=False, help="CI gate：仍有下游在读时 exit 1")
@report_options
def offboardplan(path, text, table, grace_days, archive_db, use_llm,
                 fail_blocked, lang, fmt, output) -> None:
    """下线方案 — 血缘 × 表 → 四阶段下线步骤。"""
    from seatunnel_agent.agents.data.offboard_plan import (
        plan_offboard,
        render_markdown,
    )

    try:
        plan = plan_offboard(_read(path, text, "SQL 脚本"), table,
                             grace_days=grace_days, archive_db=archive_db)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(plan, lang=lang)
    payload = plan.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.offboard_plan.advisor_llm import (
            retirement_note,
        )
        from seatunnel_agent.agents.data.offboard_plan.i18n import tp

        markdown = append_llm_note(
            payload, markdown, retirement_note(plan, lang=lang),
            "retirement_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_blocked and plan.blocked:
        fail_check(fmt, "下游仍在读 / downstream still reads: "
                   + ", ".join(sorted(plan.downstream)))


@click.command("retention")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="分区清单 CSV（带表头）或 JSONL 文件")
@click.option("--text", type=str, default=None, help="内联分区清单")
@click.option("--active-days", "active_days", type=click.IntRange(min=1),
              default=90, show_default=True,
              help="访问在该窗口内的分区视为仍在用")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草清理提案（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def retention(path, text, active_days, use_llm, fail_high,
              lang, fmt, output) -> None:
    """生命周期建议 — 分区清单 → TTL/归档/清理候选。"""
    from seatunnel_agent.agents.data.retention_policy import (
        advise_retention,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    try:
        headers, rows = parse_rows(_read(path, text, "分区清单"))
        report = advise_retention(headers, rows, active_days=active_days)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(report, lang=lang)
    payload = report.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.retention_policy.advisor_llm import (
            retention_note,
        )
        from seatunnel_agent.agents.data.retention_policy.i18n import tp

        markdown = append_llm_note(
            payload, markdown, retention_note(report, lang=lang),
            "retention_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(report.findings, fmt, label=lambda f: f.table)


@click.command("costalloc")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="用量清单 CSV（带表头）或 JSONL 文件")
@click.option("--text", type=str, default=None, help="内联用量清单")
@click.option("--storage-price", "storage_price", type=float, default=0.02,
              show_default=True, help="每 GB 存储单价")
@click.option("--compute-price", "compute_price", type=float, default=0.5,
              show_default=True, help="每计算小时单价")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草账单通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def costalloc(path, text, storage_price, compute_price, use_llm,
              fail_high, lang, fmt, output) -> None:
    """成本分摊 — 用量清单 + 单价 → 逐归属方账单。"""
    from seatunnel_agent.agents.data.cost_allocation import (
        allocate_costs,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    try:
        headers, rows = parse_rows(_read(path, text, "用量清单"))
        bill = allocate_costs(headers, rows, storage_price=storage_price,
                              compute_price=compute_price)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(bill, lang=lang)
    payload = bill.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.cost_allocation.advisor_llm import (
            billing_note,
        )
        from seatunnel_agent.agents.data.cost_allocation.i18n import tp

        markdown = append_llm_note(
            payload, markdown, billing_note(bill, lang=lang),
            "billing_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(bill.findings, fmt, label=lambda f: f.owner)


@click.command("coveragemap")
@click.option("--ddl", "ddl_path", type=click.Path(exists=True, dir_okay=False),
              required=True, help="CREATE TABLE DDL 文件")
@click.option("--rules", "rules_path",
              type=click.Path(exists=True, dir_okay=False), default=None,
              help="DQC 规则 YAML 文件（与 --contract 至少给一个）")
@click.option("--contract", "contract_path",
              type=click.Path(exists=True, dir_okay=False), default=None,
              help="契约 YAML 文件（与 --rules 至少给一个）")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/postgresql/oracle/sqlserver/doris/...)")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草补洞计划（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：热层存在裸奔表时 exit 1")
@report_options
def coveragemap(ddl_path, rules_path, contract_path, dialect, use_llm,
                fail_high, lang, fmt, output) -> None:
    """质量覆盖地图 — DDL × 闸工件 → 裸奔表点名。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.coverage_map import (
        map_coverage,
        render_markdown,
    )

    try:
        cmap = map_coverage(
            Path(ddl_path).read_text(encoding="utf-8"),
            rules_text=(Path(rules_path).read_text(encoding="utf-8")
                        if rules_path else ""),
            contract_text=(Path(contract_path).read_text(encoding="utf-8")
                           if contract_path else ""),
            dialect=dialect)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(cmap, lang=lang)
    payload = cmap.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.coverage_map.advisor_llm import (
            coverage_note,
        )
        from seatunnel_agent.agents.data.coverage_map.i18n import tp

        markdown = append_llm_note(
            payload, markdown, coverage_note(cmap, lang=lang),
            "coverage_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(cmap.findings, fmt, label=lambda f: f.table)


@click.command("compactplan")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="文件清单 CSV（带表头）或 JSONL 文件")
@click.option("--text", type=str, default=None, help="内联文件清单")
@click.option("--small-mb", "small_mb", type=float, default=32.0,
              show_default=True, help="均值低于该值记小文件")
@click.option("--target-mb", "target_mb", type=float, default=256.0,
              show_default=True, help="合并后的目标文件大小")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 做执行评审（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def compactplan(path, text, small_mb, target_mb, use_llm, fail_high,
                lang, fmt, output) -> None:
    """小文件治理 — 文件清单 → 合并候选与模板。"""
    from seatunnel_agent.agents.data.compact_plan import (
        plan_compaction,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    try:
        headers, rows = parse_rows(_read(path, text, "文件清单"))
        plan = plan_compaction(headers, rows, small_mb=small_mb,
                               target_mb=target_mb)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(plan, lang=lang)
    payload = plan.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.compact_plan.advisor_llm import (
            compaction_note,
        )
        from seatunnel_agent.agents.data.compact_plan.i18n import tp

        markdown = append_llm_note(
            payload, markdown, compaction_note(plan, lang=lang),
            "compaction_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(plan.findings, fmt, label=lambda f: f.table)


def register(cli) -> None:
    cli.add_command(assetsearch)
    cli.add_command(datadict)
    cli.add_command(assetvalue)
    cli.add_command(storagecost)
    cli.add_command(dbdiag)
    cli.add_command(grantreview)
    cli.add_command(layercheck)
    cli.add_command(capacityforecast)
    cli.add_command(contractgen)
    cli.add_command(modelreview)
    cli.add_command(duppipeline)
    cli.add_command(maskpreview)
    cli.add_command(fieldusage)
    cli.add_command(offboardplan)
    cli.add_command(retention)
    cli.add_command(costalloc)
    cli.add_command(coveragemap)
    cli.add_command(compactplan)
