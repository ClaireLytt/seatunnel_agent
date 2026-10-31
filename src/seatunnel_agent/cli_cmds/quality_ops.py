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
  seatunnel-agent datadict      -f catalog.json [--sql-file workload.sql]
  seatunnel-agent assetvalue    -f inventory.csv
"""

from __future__ import annotations

import click

from .check_runner import emit_payload as _emit
from .check_runner import fail_check, report_options
from .check_runner import read_input as _read


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

        note = review_note(result, lang=lang)
        payload["review_note"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_llm_note')}\n{note}\n"
    _emit(payload, markdown, fmt, output)
    if fail_high:
        worst = [f for f in result.findings if f.severity == "high"]
        if worst:
            fail_check(
                "HIGH " + ", ".join(f"{f.code}:{f.column}" for f in worst),
                fmt)


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

        note = drift_note(result, lang=lang)
        payload["drift_note"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_llm_note')}\n{note}\n"
    _emit(payload, markdown, fmt, output)
    if fail_high:
        worst = [f for f in result.findings if f.severity == "high"]
        if worst:
            fail_check(
                "HIGH " + ", ".join(f"{f.code}:{f.column}" for f in worst),
                fmt)


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

        note = dedup_note(result, lang=lang)
        payload["dedup_note"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_llm_note')}\n{note}\n"
    _emit(payload, markdown, fmt, output)
    if fail_dup:
        extra = result.row_dup_rows + result.pk_dup_rows + result.biz_dup_rows
        if extra:
            fail_check(f"DUPLICATES {extra} extra row(s)", fmt)


@click.command("datavolatility")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="序列文件：date,metric,value 的 CSV/JSONL")
@click.option("--text", type=str, default=None, help="内联序列行")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草波动通报（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级波动时 exit 1")
@report_options
def datavolatility(path, text, use_llm, fail_high, lang, fmt, output) -> None:
    """数据波动分析 — 时间序列 → 突增/突降/位移/走平/断档。"""
    from seatunnel_agent.agents.data.data_volatility import (
        analyze_series,
        parse_series,
        render_markdown,
    )

    try:
        result = analyze_series(parse_series(_read(path, text, "序列行")))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.data_volatility.advisor_llm import (
            volatility_note,
        )
        from seatunnel_agent.agents.data.data_volatility.i18n import tp

        note = volatility_note(result, lang=lang)
        payload["volatility_note"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_llm_note')}\n{note}\n"
    _emit(payload, markdown, fmt, output)
    if fail_high:
        worst = [f for f in result.findings if f.severity == "high"]
        if worst:
            fail_check(
                "HIGH " + ", ".join(f"{f.code}:{f.metric}" for f in worst),
                fmt)


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

        note = trace_note(result, lang=lang)
        payload["trace_note"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_llm_note')}\n{note}\n"
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

        note = repair_note(plan, lang=lang)
        payload["repair_note"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_llm_note')}\n{note}\n"
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

        note = recommend_note(result, lang=lang)
        payload["recommendation"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_llm_note')}\n{note}\n"
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

        note = grading_note(result, lang=lang)
        payload["grading_note"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_llm_note')}\n{note}\n"
    _emit(payload, markdown, fmt, output)


@click.command("datadict")
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

        note = describe_columns(result, lang=lang)
        payload["descriptions"] = note
        markdown += f"\n\n### {tp(lang, 'rpt_llm_note')}\n{note}\n"
    _emit(payload, markdown, fmt, output)
    if min_cov:
        avg = (sum(t.comment_coverage for t in result.tables)
               / len(result.tables)) if result.tables else 0.0
        if avg < min_cov:
            fail_check(f"COVERAGE {avg:.0f}% < {min_cov:g}%", fmt)
