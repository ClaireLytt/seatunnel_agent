"""建设组 CLI 命令（血缘/调度/Schema/选型等）。

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


@click.command("rollbackplan")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="流水线 SQL 脚本文件")
@click.option("--text", type=str, default=None, help="内联 SQL 脚本")
@click.option("--table", "-t", required=True, help="写坏的表")
@click.option("--partitions", "-p", "parts", type=str, default="",
              help="坏分区（逗号分隔,如 dt=2026-10-30）")
@click.option("--mode", type=click.Choice(["snapshot", "rerun",
                                           "overwrite"]),
              default="rerun", show_default=True, help="恢复方式")
@click.option("--snapshot", type=str, default="",
              help="快照表名（mode=snapshot 时）")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/postgresql/oracle/sqlserver/doris/...)")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草事故进展通报（需配置 API key）")
@report_options
def rollbackplan(path, text, table, parts, mode, snapshot, dialect,
                 use_llm, lang, fmt, output) -> None:
    """回滚编排 — 坏表 × 血缘 → 分层恢复步骤 + 验证。"""
    from seatunnel_agent.agents.data.rollback_plan import (
        plan_rollback,
        render_markdown,
    )

    partitions = [p.strip() for p in parts.split(",") if p.strip()]
    try:
        plan = plan_rollback(_read(path, text, "SQL 脚本"), table,
                             partitions=partitions, mode=mode,
                             snapshot=snapshot, dialect=dialect)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(plan, lang=lang)
    payload = plan.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.rollback_plan.advisor_llm import (
            rollback_note,
        )
        from seatunnel_agent.agents.data.rollback_plan.i18n import tp

        markdown = append_llm_note(
            payload, markdown, rollback_note(plan, lang=lang),
            "rollback_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


@click.command("schemaalign")
@click.option("--source", "-s", "src_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="源表 DDL 文件")
@click.option("--sink", "sink_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="目标表 DDL 文件")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草对齐评审（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级风险时 exit 1")
@report_options
def schemaalign(src_path, sink_path, use_llm, fail_high,
                lang, fmt, output) -> None:
    """源目 Schema 对齐 — 双 DDL → 映射风险分级。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.schema_align import (
        align_schemas,
        render_markdown,
    )

    try:
        result = align_schemas(
            Path(src_path).read_text(encoding="utf-8", errors="replace"),
            Path(sink_path).read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.schema_align.advisor_llm import (
            alignment_note,
        )
        from seatunnel_agent.agents.data.schema_align.i18n import tp

        markdown = append_llm_note(
            payload, markdown, alignment_note(result, lang=lang),
            "alignment_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(result.findings, fmt,
                     label=lambda f: f"{f.code}:{f.column}")


@click.command("alertstorm")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="告警导出文件（CSV 或 JSON 列表）")
@click.option("--text", type=str, default=None, help="内联导出")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草交接摘要（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：检出风暴窗口时 exit 1")
@report_options
def alertstorm(path, text, use_llm, fail_high, lang, fmt, output) -> None:
    """告警风暴聚合 — 导出 → 聚类 + 风暴/横跳/抑制建议。"""
    from seatunnel_agent.agents.data.alert_storm import (
        analyze_alerts,
        parse_alerts,
        render_markdown,
    )

    try:
        result = analyze_alerts(parse_alerts(_read(path, text, "导出")))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.alert_storm.advisor_llm import (
            digest_note,
        )
        from seatunnel_agent.agents.data.alert_storm.i18n import tp

        markdown = append_llm_note(
            payload, markdown, digest_note(result, lang=lang),
            "digest_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(result.findings, fmt)


@click.command("configdiff")
@click.option("--left", "-l", "left_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="左侧配置文件（如 dev）")
@click.option("--right", "right_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="右侧配置文件（如 prod）")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草发布评审意见（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级差异时 exit 1")
@report_options
def configdiff(left_path, right_path, use_llm, fail_high,
               lang, fmt, output) -> None:
    """配置漂移对比 — 双配置 → 分级语义差异。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.config_diff import (
        diff_configs,
        render_markdown,
    )

    try:
        result = diff_configs(
            Path(left_path).read_text(encoding="utf-8", errors="replace"),
            Path(right_path).read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.config_diff.advisor_llm import (
            drift_note,
        )
        from seatunnel_agent.agents.data.config_diff.i18n import tp

        markdown = append_llm_note(
            payload, markdown, drift_note(result, lang=lang),
            "drift_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(result.entries, fmt, label=lambda e: e.key)


@click.command("scheduleadvisor")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="排程计划 JSON 文件")
@click.option("--text", type=str, default=None, help="内联计划 JSON")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草排程通报（需配置 API key）")
@click.option("--fail-on-breach", "fail_breach", is_flag=True, default=False,
              help="CI gate：SLA 余量为负时 exit 1")
@report_options
def scheduleadvisor(path, text, use_llm, fail_breach,
                    lang, fmt, output) -> None:
    """调度窗口优化 — 计划 → 时间线 + 关键路径 + SLA 余量。"""
    from seatunnel_agent.agents.data.schedule_advisor import (
        advise_schedule,
        parse_plan,
        render_markdown,
    )

    try:
        result = advise_schedule(parse_plan(_read(path, text, "计划")))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.schedule_advisor.advisor_llm import (
            schedule_note,
        )
        from seatunnel_agent.agents.data.schedule_advisor.i18n import tp

        markdown = append_llm_note(
            payload, markdown, schedule_note(result, lang=lang),
            "schedule_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_breach and result.margin_min is not None \
            and result.margin_min < 0:
        fail_check(f"SLA BREACH margin {result.margin_min:g} min", fmt)


@click.command("taskfailure")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="失败任务导出文件（CSV 或 JSON 列表）")
@click.option("--text", type=str, default=None, help="内联导出")
@click.option("--history", "history_path", type=click.Path(dir_okay=False),
              default=None,
              help="失败台账：总数与各归因计数追加到该 jsonl 并打印漂移")
@click.option("--trend", "trend_n", type=click.IntRange(min=2), default=None,
              help="恶化趋势：台账（含本次）最近 N 次失败总数逐次上涨时"
                   "在报告点名（需配合 --history）")
@click.option("--fail-on-trend", "fail_on_trend", is_flag=True,
              default=False, help="CI gate：检出恶化趋势时 exit 1")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草失败通报（需配置 API key）")
@report_options
def taskfailure(path, text, history_path, trend_n, fail_on_trend, use_llm,
                lang, fmt, output) -> None:
    """任务失败归因 — 失败导出 → 根因聚类 + 重试判定；--history 记台账。"""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.data.task_failure import (
        classify_failures,
        parse_failures,
        render_markdown,
    )

    require_with((trend_n or fail_on_trend) and not history_path,
                 "--trend / --fail-on-trend", "--history")
    require_with(fail_on_trend and not trend_n, "--fail-on-trend",
                 "--trend N")
    try:
        result = classify_failures(parse_failures(_read(path, text, "导出")))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(result, lang=lang)
    payload = result.to_dict()
    trend = None
    if trend_n:
        from .check_runner import rising_trend

        ledger = (Path(history_path).read_text(encoding="utf-8",
                                               errors="replace")
                  if Path(history_path).is_file() else "")
        entries = [_json.loads(ln) for ln in ledger.splitlines()
                   if ln.strip()]
        entries.append({"total": result.total})
        trend = rising_trend(entries, "total", trend_n)
        if trend:
            payload["trend"] = trend
            markdown += (f"\n\n**failures rising** — "
                         f"{trend['from_v']:g} -> {trend['to_v']:g} "
                         f"over {trend['records']} run(s) "
                         f"(+{trend['growth_pct']}%)")
    if use_llm:
        from seatunnel_agent.agents.data.task_failure.advisor_llm import (
            failure_note,
        )
        from seatunnel_agent.agents.data.task_failure.i18n import tp

        markdown = append_llm_note(
            payload, markdown, failure_note(result, lang=lang),
            "failure_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if history_path:
        _track_history(history_path, {
            "total": result.total,
            **{f"cause_{c}": n for c, n in result.causes.items()}},
            worse_key="total")
    if fail_on_trend and trend:
        fail_check(f"TREND failures {trend['from_v']:g} -> "
                   f"{trend['to_v']:g} over {trend['records']} run(s)",
                   fmt)


@click.command("sqldiff")
@click.option("--old", "old_path", type=click.Path(exists=True, dir_okay=False),
              required=True, help="旧版 SQL 文件")
@click.option("--new", "new_path", type=click.Path(exists=True, dir_okay=False),
              required=True, help="新版 SQL 文件")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/postgresql/oracle/sqlserver/doris/...)")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草变更评审（需配置 API key）")
@click.option("--fail-on-breaking", "fail_breaking", is_flag=True,
              default=False, help="CI gate：存在破坏级差异时 exit 1")
@report_options
def sqldiff(old_path, new_path, dialect, use_llm, fail_breaking,
            lang, fmt, output) -> None:
    """SQL 语义对比 — 两版取数 SQL → 分级语义差异。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.sql_diff import (
        diff_sql,
        render_markdown,
    )

    try:
        report = diff_sql(Path(old_path).read_text(encoding="utf-8"),
                          Path(new_path).read_text(encoding="utf-8"),
                          dialect=dialect)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(report, lang=lang)
    payload = report.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.sql_diff.advisor_llm import (
            change_note,
        )
        from seatunnel_agent.agents.data.sql_diff.i18n import tp

        markdown = append_llm_note(
            payload, markdown, change_note(report, lang=lang),
            "change_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_breaking:
        broken = [f for f in report.findings if f.severity == "breaking"]
        if broken:
            fail_check(fmt, "存在破坏级差异 / breaking differences: "
                       + ", ".join(f"{f.target}:{f.kind}" for f in broken))


@click.command("ddlevolve")
@click.option("--old", "old_path", type=click.Path(exists=True, dir_okay=False),
              required=True, help="旧版 DDL 快照文件")
@click.option("--new", "new_path", type=click.Path(exists=True, dir_okay=False),
              required=True, help="新版 DDL 快照文件")
@click.option("--dialect",
              type=click.Choice(["hive", "spark", "maxcompute",
                                 "mysql", "postgres", "oracle",
                                 "sqlserver", "doris"]),
              default="hive", show_default=True, help="目标方言")
@click.option("--script-out", "script_out", type=click.Path(dir_okay=False),
              default=None, help="把迁移脚本另存到该文件")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草上线建议（需配置 API key）")
@report_options
def ddlevolve(old_path, new_path, dialect, script_out, use_llm,
              lang, fmt, output) -> None:
    """DDL 迁移脚本 — 新旧快照 → 可执行 ALTER 脚本。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.ddl_evolve import (
        build_migration,
        render_markdown,
    )

    try:
        plan = build_migration(
            Path(old_path).read_text(encoding="utf-8"),
            Path(new_path).read_text(encoding="utf-8"), dialect=dialect)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    if script_out:
        Path(script_out).write_text(plan.to_script(), encoding="utf-8")
    markdown = render_markdown(plan, lang=lang)
    payload = plan.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.ddl_evolve.advisor_llm import (
            migration_note,
        )
        from seatunnel_agent.agents.data.ddl_evolve.i18n import tp

        markdown = append_llm_note(
            payload, markdown, migration_note(plan, lang=lang),
            "migration_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


@click.command("seatunnelgen")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="CREATE TABLE DDL 文件")
@click.option("--text", type=str, default=None, help="内联 DDL")
@click.option("--source", "-s", required=True,
              help="源连接器,如 MySQL-CDC / Jdbc / Kafka")
@click.option("--sink", "-k", required=True,
              help="目标连接器,如 Doris / Hive / ClickHouse")
@click.option("--job-mode", "job_mode",
              type=click.Choice(["BATCH", "STREAMING", ""]), default="",
              help="作业模式,留空自动（CDC 源 → STREAMING）")
@click.option("--parallelism", type=click.IntRange(min=1), default=2,
              show_default=True, help="env.parallelism")
@click.option("--conf-out", "conf_out", type=click.Path(dir_okay=False),
              default=None, help="把 job.conf 另存到该文件")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草运行前评审（需配置 API key）")
@report_options
def seatunnelgen(path, text, source, sink, job_mode, parallelism,
                 conf_out, use_llm, lang, fmt, output) -> None:
    """作业配置生成 — 表 DDL + 连接器对 → 零错误 job.conf。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.seatunnel_gen import (
        generate_config,
        render_markdown,
    )

    try:
        draft = generate_config(_read(path, text, "DDL"), source, sink,
                                job_mode=job_mode,
                                parallelism=parallelism)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    if conf_out:
        Path(conf_out).write_text(draft.hocon_text, encoding="utf-8")
    markdown = render_markdown(draft, lang=lang)
    payload = draft.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.seatunnel_gen.advisor_llm import (
            job_note,
        )
        from seatunnel_agent.agents.data.seatunnel_gen.i18n import tp

        markdown = append_llm_note(
            payload, markdown, job_note(draft, lang=lang),
            "job_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


@click.command("daggen")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="流水线 SQL 脚本文件")
@click.option("--text", type=str, default=None, help="内联 SQL 脚本")
@click.option("--dag-id", "dag_id", default="pipeline", show_default=True,
              help="Airflow dag_id（标识符）")
@click.option("--schedule", default="0 2 * * *", show_default=True,
              help="cron 调度表达式")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/postgresql/oracle/sqlserver/doris/...)")
@click.option("--engine", default="airflow", show_default=True,
              type=click.Choice(["airflow", "dolphinscheduler",
                                 "azkaban"]),
              help="调度引擎（airflow=dag.py / dolphinscheduler=定义 "
                   "JSON / azkaban=.flow YAML）")
@click.option("--py-out", "py_out", type=click.Path(dir_okay=False),
              default=None, help="把生成的调度文件另存到该文件")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草部署前评审（需配置 API key）")
@report_options
def daggen(path, text, dag_id, schedule, dialect, engine, py_out,
           use_llm, lang, fmt, output) -> None:
    """调度文件生成 — 流水线 SQL → Airflow/DolphinScheduler/Azkaban。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.dag_gen import (
        generate_dag,
        render_markdown,
    )

    try:
        draft = generate_dag(_read(path, text, "SQL 脚本"), dag_id=dag_id,
                             schedule=schedule, dialect=dialect,
                             engine=engine)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    if py_out:
        Path(py_out).write_text(draft.python_text, encoding="utf-8")
    markdown = render_markdown(draft, lang=lang)
    payload = draft.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.dag_gen.advisor_llm import (
            schedule_note,
        )
        from seatunnel_agent.agents.data.dag_gen.i18n import tp

        markdown = append_llm_note(
            payload, markdown, schedule_note(draft, lang=lang),
            "schedule_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


@click.command("topicschema")
@click.option("--old", "old_path", type=click.Path(exists=True, dir_okay=False),
              required=True, help="旧版 Schema JSON 文件（Avro 或 JSON Schema）")
@click.option("--new", "new_path", type=click.Path(exists=True, dir_okay=False),
              required=True, help="新版 Schema JSON 文件")
@click.option("--mode", type=click.Choice(["backward", "forward", "full"]),
              default="backward", show_default=True, help="兼容模式")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草发布通报（需配置 API key）")
@click.option("--fail-on-breaking", "fail_breaking", is_flag=True,
              default=False, help="CI gate：存在 breaking 变更时 exit 1")
@report_options
def topicschema(old_path, new_path, mode, use_llm, fail_breaking,
                lang, fmt, output) -> None:
    """消息 Schema 对比 — 两版 Avro/JSON Schema → 兼容结论。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.topic_schema import (
        diff_topic_schemas,
        render_markdown,
    )

    try:
        report = diff_topic_schemas(
            Path(old_path).read_text(encoding="utf-8"),
            Path(new_path).read_text(encoding="utf-8"), mode=mode)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(report, lang=lang)
    payload = report.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.topic_schema.advisor_llm import (
            rollout_note,
        )
        from seatunnel_agent.agents.data.topic_schema.i18n import tp

        markdown = append_llm_note(
            payload, markdown, rollout_note(report, lang=lang),
            "rollout_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_breaking and not report.compatible:
        broken = [f.fld for f in report.findings
                  if f.severity == "breaking"]
        fail_check(fmt, "存在破坏兼容的变更 / breaking changes: "
                   + ", ".join(broken))


@click.command("partitionplan")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="数据样例 CSV（带表头）或 JSONL 文件")
@click.option("--text", type=str, default=None, help="内联样例行")
@click.option("--queries", "-q", "queries_path",
              type=click.Path(exists=True, dir_okay=False), required=True,
              help="将要打在这张表上的查询 SQL 文件")
@click.option("--dialect", default="hive", show_default=True,
              help="SQL 方言 (hive/spark/mysql/postgresql/oracle/sqlserver/doris/...)")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 做选型评审（需配置 API key）")
@click.option("--fail-on-medium", "fail_medium", is_flag=True,
              default=False,
              help="CI gate：存在 medium 级发现（无合格键/热列不适配）时 exit 1")
@report_options
def partitionplan(path, text, queries_path, dialect, use_llm, fail_medium,
                  lang, fmt, output) -> None:
    """分区键选型 — 样例 + 负载 → 候选排名与 DDL 子句。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.partition_plan import (
        plan_partitions,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    try:
        headers, rows = parse_rows(_read(path, text, "样例行"))
        plan = plan_partitions(
            headers, rows,
            Path(queries_path).read_text(encoding="utf-8"),
            dialect=dialect)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(plan, lang=lang)
    payload = plan.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.partition_plan.advisor_llm import (
            plan_note,
        )
        from seatunnel_agent.agents.data.partition_plan.i18n import tp

        markdown = append_llm_note(
            payload, markdown, plan_note(plan, lang=lang),
            "plan_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_medium:
        bad = [f.code for f in plan.findings if f.severity == "medium"]
        if bad:
            fail_check(fmt, "选型存在风险 / plan risks: " + ", ".join(bad))


@click.command("incidentreview")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="事故事件日志 CSV（带表头）或 JSONL 文件")
@click.option("--text", type=str, default=None, help="内联事件日志")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 起草复盘文档（需配置 API key）")
@click.option("--fail-on-high", "fail_high", is_flag=True, default=False,
              help="CI gate：存在 high 级发现时 exit 1")
@report_options
def incidentreview(path, text, use_llm, fail_high,
                   lang, fmt, output) -> None:
    """事故复盘 — 事件日志 → 时间线与用时指标。"""
    from seatunnel_agent.agents.data.incident_review import (
        render_markdown,
        review_incident,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    try:
        headers, rows = parse_rows(_read(path, text, "事件日志"))
        review = review_incident(headers, rows)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    markdown = render_markdown(review, lang=lang)
    payload = review.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.incident_review.advisor_llm import (
            postmortem_note,
        )
        from seatunnel_agent.agents.data.incident_review.i18n import tp

        markdown = append_llm_note(
            payload, markdown, postmortem_note(review, lang=lang),
            "postmortem_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)
    if fail_high:
        fail_on_high(review.findings, fmt, label=lambda f: f.code)


@click.command("avro2ddl")
@click.option("--file", "-f", "path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="Schema JSON 文件（Avro record 或 JSON Schema）")
@click.option("--text", type=str, default=None, help="内联 Schema JSON")
@click.option("--table", "-t", default="",
              help="目标表名（默认取 record 的 namespace.name）")
@click.option("--dialect",
              type=click.Choice(["hive", "spark", "maxcompute",
                                 "mysql", "postgres", "oracle",
                                 "sqlserver", "doris"]),
              default="hive", show_default=True, help="目标方言")
@click.option("--ddl-out", "ddl_out", type=click.Path(dir_okay=False),
              default=None, help="把建表语句另存到该文件")
@click.option("--llm", "use_llm", is_flag=True, default=False,
              help="额外请求 LLM 做落地评审（需配置 API key）")
@report_options
def avro2ddl(path, text, table, dialect, ddl_out, use_llm,
             lang, fmt, output) -> None:
    """消息 Schema 建表 — Avro/JSON Schema → CREATE TABLE。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.avro2ddl import (
        convert_schema,
        render_markdown,
    )

    try:
        draft = convert_schema(_read(path, text, "Schema"), table=table,
                               dialect=dialect)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    if ddl_out:
        Path(ddl_out).write_text(draft.ddl_text + "\n", encoding="utf-8")
    markdown = render_markdown(draft, lang=lang)
    payload = draft.to_dict()
    if use_llm:
        from seatunnel_agent.agents.data.avro2ddl.advisor_llm import (
            landing_note,
        )
        from seatunnel_agent.agents.data.avro2ddl.i18n import tp

        markdown = append_llm_note(
            payload, markdown, landing_note(draft, lang=lang),
            "landing_note", tp(lang, "rpt_llm_note"))
    _emit(payload, markdown, fmt, output)


def register(cli) -> None:
    cli.add_command(taskfailure)
    cli.add_command(scheduleadvisor)
    cli.add_command(configdiff)
    cli.add_command(alertstorm)
    cli.add_command(schemaalign)
    cli.add_command(rollbackplan)
    cli.add_command(sqldiff)
    cli.add_command(ddlevolve)
    cli.add_command(seatunnelgen)
    cli.add_command(daggen)
    cli.add_command(topicschema)
    cli.add_command(partitionplan)
    cli.add_command(incidentreview)
    cli.add_command(avro2ddl)
