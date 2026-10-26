from __future__ import annotations

import os

import click

from ..common.cli_common import _ensure_utf8_stdio, console


@click.command(name="t2s-bench")
@click.option("--ddl", type=click.Path(exists=True), required=True,
              help="schema DDL 文件（表白名单）")
@click.option("--bench", "-b", "bench_file", type=click.Path(exists=True), required=True,
              help="评测集 JSONL（{question, tables} 每行一条）")
@click.option("--mode", type=click.Choice(["keyword", "hybrid", "both"]),
              default="both", show_default=True, help="评测模式")
@click.option("--gate", is_flag=True,
              help="回归门禁：hybrid Top3 低于 keyword 时退出码 1")
def t2s_bench(ddl: str, bench_file: str, mode: str, gate: bool) -> None:
    """Text2SQL 表检索评测：对比 keyword-only 与 hybrid 的 Top1/Top3 命中率。"""
    _ensure_utf8_stdio()
    from seatunnel_agent.agents.data.text2sql.bench import (
        load_bench,
        render_bench_report,
        run_bench,
    )
    from seatunnel_agent.agents.data.text2sql.schema import SchemaStore

    store = SchemaStore.from_file(ddl)
    try:
        cases = load_bench(bench_file)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    if not cases:
        raise click.ClickException("评测集为空")

    modes = ["keyword", "hybrid"] if mode == "both" else [mode]
    results = [run_bench(store, cases, m) for m in modes]
    console.print(render_bench_report(results))

    if gate and len(results) == 2:
        kw, hy = results[0], results[1]
        if hy.top3 < kw.top3:
            console.print(
                f"[red]回归门禁失败: hybrid Top3 {hy.top3_rate:.1%} < "
                f"keyword {kw.top3_rate:.1%}[/red]"
            )
            raise SystemExit(1)
        console.print("[green]回归门禁通过: hybrid 不低于 keyword[/green]")


@click.command(name="t2s-index-values")
@click.option("--ddl", type=click.Path(exists=True), default=None,
              help="schema DDL 文件（默认 SCHEMA_DDL_PATH / config/schema_ddl.sql）")
@click.option("--ds-type", type=str, default="sqlite", show_default=True,
              help="数据源类型")
@click.option("--database", type=str, default="",
              help="sqlite 数据库文件路径（仅 --ds-type sqlite 需要）")
@click.option("--connection", type=str, default="",
              help="已保存连接的名称（settings 页配置），优先于环境变量")
def t2s_index_values(ddl: str | None, ds_type: str, database: str,
                     connection: str) -> None:
    """构建值级检索索引：采样低基数字符串列的枚举值（问题里的取值 → 表/列/字面量）。"""
    _ensure_utf8_stdio()
    import os as _os
    from pathlib import Path

    from seatunnel_agent.agents.data.text2sql.executor import create_executor
    from seatunnel_agent.agents.data.text2sql.retrieval import schema_hash
    from seatunnel_agent.agents.data.text2sql.schema import SchemaStore
    from seatunnel_agent.agents.data.text2sql.subscriptions import resolve_db_config
    from seatunnel_agent.agents.data.text2sql.values import ValueIndex

    ddl_path = ddl or _os.getenv("SCHEMA_DDL_PATH", "config/schema_ddl.sql")
    if not Path(ddl_path).is_file():
        raise click.ClickException(f"DDL 文件不存在: {ddl_path}")
    store = SchemaStore.from_file(ddl_path)
    db_config = resolve_db_config({
        "ds_type": ds_type, "connection": connection, "database": database,
    })
    if db_config is None:
        raise click.ClickException("无法解析数据库连接（连接名/环境变量）")
    executor = create_executor(db_config)
    index = ValueIndex.build(executor, store)
    if len(index) == 0:
        console.print("[yellow]未采样到任何值（分区表被跳过；检查列类型/数据）[/yellow]")
        return
    path = index.save(schema_hash(store))
    n_tables = len(index.data)
    console.print(
        f"[green]值索引已构建: {n_tables} 张表 / {len(index)} 列 -> {path}[/green]"
    )


@click.command(name="t2s-mcp")
@click.option("--ddl", type=click.Path(exists=True), default=None,
              help="schema DDL 文件（默认 SCHEMA_DDL_PATH / config/schema_ddl.sql）")
@click.option("--metrics", "metrics_file", type=click.Path(exists=True), default=None,
              help="指标定义文件（默认 config/metrics.yaml）")
@click.option("--ds-type", type=str, default="hive", show_default=True,
              help="SQL 方言 / 数据源类型")
@click.option("--allow-execute", is_flag=True,
              help="开放 execute_readonly_sql 工具（默认只出 SQL 不执行）")
@click.option("--database", type=str, default="",
              help="sqlite 数据库文件路径（仅 --ds-type sqlite 需要）")
def t2s_mcp(ddl: str | None, metrics_file: str | None, ds_type: str,
            allow_execute: bool, database: str) -> None:
    """以 MCP server（stdio）暴露 Chat BI 确定性能力：表检索、指标口径、指标 SQL 展开。"""
    from seatunnel_agent.agents.data.text2sql.mcp_server import create_mcp_server

    try:
        server = create_mcp_server(
            ddl_path=ddl or "", metrics_path=metrics_file or "",
            ds_type=ds_type, allow_execute=allow_execute, database=database,
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc))
    server.run()


@click.group(name="t2s-sub")
def t2s_sub() -> None:
    """Chat BI 订阅：定时执行指标/收藏查询并推送飞书卡片。"""


@t2s_sub.command("list")
def t2s_sub_list() -> None:
    """列出全部订阅及其上次执行状态。"""
    _ensure_utf8_stdio()
    from seatunnel_agent.agents.data.text2sql.subscriptions import SubscriptionStore

    subs = SubscriptionStore().list()
    if not subs:
        console.print("暂无订阅（用 t2s-sub add 创建）")
        return
    from rich.table import Table
    table = Table(title=f"订阅（{len(subs)} 个）")
    for col in ("id", "名称", "cron", "来源", "启用", "上次执行", "状态"):
        table.add_column(col)
    for s in subs:
        source = (s.get("metric") if s.get("source_type") == "metric"
                  else f"fav:{s.get('favorite_id')}")
        table.add_row(
            s.get("id", ""), s.get("name", ""), s.get("cron", ""),
            source or "", "✓" if s.get("enabled", True) else "✗",
            s.get("last_run_at", "") or "-", s.get("last_status", "") or "-",
        )
    console.print(table)


@t2s_sub.command("add")
@click.option("--name", required=True, help="订阅名称")
@click.option("--cron", "cron_expr", required=True,
              help="5 字段 cron：分 时 日 月 周（周 0=周一）")
@click.option("--metric", default="", help="指标名（与 --favorite 二选一）")
@click.option("--favorite", "favorite_id", default="", help="收藏查询 ID")
@click.option("--dim", "-d", "dims", multiple=True, help="下钻维度（可多次，仅指标订阅）")
@click.option("--lookback", type=int, default=1, show_default=True,
              help="回看天数：查询 [今天-N, 昨天]（仅指标订阅）")
@click.option("--param", "-p", "params", multiple=True,
              help="收藏参数 key=value（可多次；内置宏 today/yesterday/*_pt 自动生效）")
@click.option("--ds-type", default="hive", show_default=True)
@click.option("--connection", default="", help="连接预设名（设置页保存的连接）")
@click.option("--database", default="", help="sqlite 数据库路径（仅 sqlite）")
@click.option("--webhook", default="", help="飞书 incoming webhook URL")
@click.option("--watch", is_flag=True,
              help="异动监控订阅：昨天 vs 参照期,变动超阈值才推送告警")
@click.option("--threshold", type=float, default=10.0, show_default=True,
              help="异动阈值百分比（仅 --watch）")
@click.option("--watch-mode", type=click.Choice(["dod", "wow", "model"]),
              default="dod", show_default=True,
              help="参照期：dod=前一天, wow=上周同日, "
                   "model=预测基线95%区间（仅 --watch；model 忽略阈值）")
def t2s_sub_add(name: str, cron_expr: str, metric: str, favorite_id: str,
                dims: tuple[str, ...], lookback: int, params: tuple[str, ...],
                ds_type: str, connection: str, database: str, webhook: str,
                watch: bool, threshold: float, watch_mode: str) -> None:
    """新建订阅（--metric 定时推数 / --metric --watch 异动告警 / --favorite 收藏推数）。"""
    _ensure_utf8_stdio()
    from seatunnel_agent.agents.data.text2sql.subscriptions import SubscriptionStore

    if bool(metric) == bool(favorite_id):
        raise click.UsageError("--metric 与 --favorite 必须二选一")
    if watch and not metric:
        raise click.UsageError("--watch 只能与 --metric 搭配")
    param_map: dict[str, str] = {}
    for p in params:
        if "=" not in p:
            raise click.UsageError(f"--param 格式应为 key=value: {p}")
        k, v = p.split("=", 1)
        param_map[k.strip()] = v
    if watch:
        source_type = "metric_watch"
    else:
        source_type = "metric" if metric else "favorite"
    try:
        entry = SubscriptionStore().add(
            name=name, cron=cron_expr,
            source_type=source_type,
            metric=metric, dimensions=list(dims), lookback_days=lookback,
            favorite_id=favorite_id, params=param_map,
            threshold_pct=threshold, watch_mode=watch_mode,
            ds_type=ds_type, connection=connection, database=database,
            webhook_url=webhook,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))
    console.print(f"[green]已创建订阅 {entry['id']}: {entry['name']}[/green]")


@t2s_sub.command("rm")
@click.argument("sub_id")
def t2s_sub_rm(sub_id: str) -> None:
    """删除订阅。"""
    from seatunnel_agent.agents.data.text2sql.subscriptions import SubscriptionStore

    if not SubscriptionStore().delete(sub_id):
        raise click.ClickException(f"订阅 '{sub_id}' 不存在")
    console.print("[green]已删除[/green]")


@t2s_sub.command("enable")
@click.argument("sub_id")
@click.option("--off", is_flag=True, help="停用而非启用")
def t2s_sub_enable(sub_id: str, off: bool) -> None:
    """启用/停用订阅。"""
    from seatunnel_agent.agents.data.text2sql.subscriptions import SubscriptionStore

    if not SubscriptionStore().set_enabled(sub_id, not off):
        raise click.ClickException(f"订阅 '{sub_id}' 不存在")
    console.print(f"[green]已{'停用' if off else '启用'}[/green]")


@t2s_sub.command("run")
@click.argument("sub_id")
def t2s_sub_run(sub_id: str) -> None:
    """立即执行一次订阅（不等 cron）。"""
    _ensure_utf8_stdio()
    from seatunnel_agent.agents.data.text2sql.subscriptions import (
        SubscriptionStore,
        run_subscription,
    )

    store = SubscriptionStore()
    sub = store.get(sub_id)
    if sub is None:
        raise click.ClickException(f"订阅 '{sub_id}' 不存在")
    outcome = run_subscription(sub)
    store.record_run(sub_id, outcome.get("status", "error"), outcome.get("error", ""))
    if outcome["status"] == "success":
        console.print(f"[green]执行成功: {outcome['row_count']} 行[/green]")
        console.print(outcome["sql"])
    else:
        console.print(f"[red]执行失败: {outcome.get('error', '')}[/red]")
        raise SystemExit(1)


@click.command(name="t2s-cron")
@click.option("--once", is_flag=True, help="只检查一次到期订阅后退出（供外部调度器调用）")
@click.option("--tick", type=int, default=20, show_default=True, help="轮询间隔秒")
def t2s_cron(once: bool, tick: int) -> None:
    """订阅调度器：常驻轮询 cron 到期的订阅并执行（无 UI 部署用）。"""
    _ensure_utf8_stdio()
    import time as _time

    from seatunnel_agent.agents.data.text2sql.subscriptions import Scheduler

    scheduler = Scheduler(tick_seconds=tick)
    if once:
        fired = scheduler.check_once()
        console.print(f"到期执行 {len(fired)} 个订阅" + (f": {', '.join(fired)}" if fired else ""))
        return
    console.print(f"订阅调度器已启动（每 {tick}s 检查一次，Ctrl+C 退出）")
    scheduler.start()
    try:
        while True:
            _time.sleep(3600)
    except KeyboardInterrupt:
        scheduler.stop()
        console.print("已退出")


@click.command(name="t2s-eval")
@click.option("--dataset", type=click.Path(exists=True), required=True,
              help="评测集 JSONL（{question, golden_sql} 每行一条）")
@click.option("--ddl", type=click.Path(exists=True), default=None,
              help="schema DDL（sqlite 缺省时自动内省）")
@click.option("--ds-type", default="sqlite", show_default=True)
@click.option("--database", default="", help="sqlite 数据库路径")
@click.option("--connection", default="", help="连接预设名（设置页保存的连接）")
@click.option("--limit", type=int, default=0, help="只评前 N 题（控成本试跑）")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="报告写入文件")
@click.pass_context
def t2s_eval(ctx: click.Context, dataset: str, ddl: str | None, ds_type: str,
             database: str, connection: str, limit: int,
             output: str | None) -> None:
    """Text2SQL 端到端评测：问题→agent(真实 LLM)→结果集 与 golden SQL 对比。

    换 --model/--provider 重跑即可做多模型准确率对比。
    """
    _ensure_utf8_stdio()
    from seatunnel_agent.agents.data.text2sql.evaluate import (
        load_dataset,
        make_agent_runner,
        render_eval_report,
        run_eval,
    )
    from seatunnel_agent.agents.data.text2sql.metrics import load_metric_store
    from seatunnel_agent.agents.data.text2sql.schema import SchemaStore
    from seatunnel_agent.agents.data.text2sql.subscriptions import resolve_db_config

    try:
        settings = _settings_with_overrides(ctx)
    except RuntimeError as exc:
        raise click.ClickException(str(exc))

    try:
        cases = load_dataset(dataset)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    if limit > 0:
        cases = cases[:limit]
    if not cases:
        raise click.ClickException("评测集为空")

    db_config = resolve_db_config({
        "ds_type": ds_type, "connection": connection, "database": database,
    })
    if db_config is None:
        raise click.ClickException("无法解析数据库连接")

    if ddl:
        store = SchemaStore.from_file(ddl)
    else:
        from seatunnel_agent.agents.data.text2sql.executor import create_executor
        store = SchemaStore.from_db(create_executor(db_config))
    if len(store) == 0:
        raise click.ClickException("未加载到任何表")
    metric_store, _errs = load_metric_store(store)

    runner = make_agent_runner(
        settings, store, ds_type, db_config,
        metric_store=metric_store if len(metric_store) else None,
    )
    console.print(f"共 {len(cases)} 题,模型 {settings.model_name},开始评测...")
    report = run_eval(cases, runner, db_config, store=store)
    text = render_eval_report(report, model_name=settings.model_name)
    console.print(text)
    if output:
        from pathlib import Path as _P
        _P(output).write_text(text, encoding="utf-8")
        console.print(f"[green]报告已写入 {output}[/green]")


def _settings_with_overrides(ctx: click.Context):
    """load_settings honoring the global --model/--provider overrides."""
    model = (ctx.obj or {}).get("model") if ctx.obj else None
    provider = (ctx.obj or {}).get("provider") if ctx.obj else None
    old_model = os.environ.get("MODEL_NAME")
    old_provider = os.environ.get("LLM_PROVIDER")
    try:
        if model:
            os.environ["MODEL_NAME"] = model
        if provider:
            os.environ["LLM_PROVIDER"] = provider
        from ..common.config import load_settings
        return load_settings()
    finally:
        for key, old in (("MODEL_NAME", old_model), ("LLM_PROVIDER", old_provider)):
            if os.environ.get(key) != (old or ""):
                if old is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old


@click.group()
def dqc() -> None:
    """DQC 数据质量：规则化表级检查（行数/空值率/唯一性/枚举域）。"""


@dqc.command("validate")
@click.option("--rules", "-r", "rules_file", type=click.Path(exists=True),
              required=True, help="DQC 规则 YAML")
@click.option("--ddl", type=click.Path(exists=True), required=True,
              help="schema DDL（表白名单），交叉校验表/列存在性")
def dqc_validate(rules_file: str, ddl: str) -> None:
    """校验规则与 DDL 的一致性（CI 门禁：有错误时退出码 1）。"""
    _ensure_utf8_stdio()
    from seatunnel_agent.agents.data.data_quality import load_rules, validate_rules
    from seatunnel_agent.agents.data.text2sql.schema import SchemaStore

    rules, errors = load_rules(rules_file)
    errors += validate_rules(rules, SchemaStore.from_file(ddl))
    if errors:
        for err in errors:
            console.print(f"[red]{err}[/red]")
        raise SystemExit(1)
    n_checks = sum(len(r.checks) for r in rules)
    console.print(f"[green]校验通过：{len(rules)} 张表 / {n_checks} 项检查[/green]")


@dqc.command("run")
@click.option("--rules", "-r", "rules_file", type=click.Path(exists=True),
              required=True, help="DQC 规则 YAML")
@click.option("--ddl", type=click.Path(exists=True), default=None,
              help="schema DDL（给出时检查 SQL 也过白名单校验）")
@click.option("--ds-type", default="hive", show_default=True)
@click.option("--database", default="", help="sqlite 数据库路径（仅 sqlite）")
@click.option("--connection", default="", help="连接预设名（设置页保存的连接）")
@click.option("--webhook", default="", help="有不通过项时推送飞书告警卡片")
@click.option("--fail-on-violation/--no-fail-on-violation", default=True,
              show_default=True, help="有不通过/异常项时退出码 1（CI 门禁）")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="报告写入文件")
def dqc_run(rules_file: str, ddl: str | None, ds_type: str, database: str,
            connection: str, webhook: str, fail_on_violation: bool,
            output: str | None) -> None:
    """执行全部质量检查并输出报告。"""
    _ensure_utf8_stdio()
    from seatunnel_agent.agents.data.data_quality import (
        load_rules,
        render_report,
        run_checks,
    )
    from seatunnel_agent.agents.data.data_quality.runner import push_failures
    from seatunnel_agent.agents.data.text2sql.executor import create_executor
    from seatunnel_agent.agents.data.text2sql.subscriptions import resolve_db_config

    rules, errors = load_rules(rules_file)
    if errors:
        for err in errors:
            console.print(f"[red]{err}[/red]")
        raise SystemExit(1)
    if not rules:
        raise click.ClickException("规则文件为空")

    schema_store = None
    if ddl:
        from seatunnel_agent.agents.data.text2sql.schema import SchemaStore
        schema_store = SchemaStore.from_file(ddl)

    db_config = resolve_db_config({
        "ds_type": ds_type, "connection": connection, "database": database,
    })
    if db_config is None:
        raise click.ClickException(
            "无法解析数据库连接（--connection 预设名、--database 或环境变量）")

    results = run_checks(rules, create_executor(db_config),
                         schema_store=schema_store, ds_type=ds_type)
    report = render_report(results)
    console.print(report)
    if output:
        from pathlib import Path as _P
        _P(output).write_text(report, encoding="utf-8")
        console.print(f"[green]报告已写入 {output}[/green]")
    if webhook:
        ok, msg = push_failures(results, webhook)
        if not ok:
            console.print(f"[yellow]告警推送失败: {msg}[/yellow]")
    bad = sum(1 for r in results if r.status != "pass")
    if bad and fail_on_violation:
        raise SystemExit(1)


def _load_metrics_for_cli(metrics_file: str | None, ddl: str | None):
    """Shared loader for the metrics subcommands: (store, errors)."""
    from seatunnel_agent.agents.data.text2sql.metrics import load_metric_store

    schema_store = None
    if ddl:
        from seatunnel_agent.agents.data.text2sql.schema import SchemaStore
        schema_store = SchemaStore.from_file(ddl)
    return load_metric_store(schema_store, path=metrics_file)


@click.group()
def metrics() -> None:
    """指标语义层：查看/校验 metrics.yaml 中的指标口径定义（Chat BI）。"""


@metrics.command("list")
@click.option("--file", "-f", "metrics_file", type=click.Path(exists=True),
              default=None, help="指标定义文件（默认 config/metrics.yaml）")
def metrics_list(metrics_file: str | None) -> None:
    """列出全部已定义指标。"""
    _ensure_utf8_stdio()
    store, errors = _load_metrics_for_cli(metrics_file, None)
    for err in errors:
        console.print(f"[yellow]警告: {err}[/yellow]")
    if len(store) == 0:
        console.print("未找到任何指标定义（config/metrics.yaml）")
        return
    from rich.table import Table
    table = Table(title=f"指标目录（{len(store)} 个）")
    for col in ("name", "展示名", "类型", "口径", "单位", "负责人"):
        table.add_column(col)
    for m in store.metrics:
        caliber = (f"{m.numerator} / {m.denominator}" if m.is_ratio
                   else f"{m.expression} FROM {m.table}")
        table.add_row(m.name, m.display_name, m.metric_type, caliber, m.unit, m.owner)
    console.print(table)


@metrics.command("show")
@click.argument("name")
@click.option("--file", "-f", "metrics_file", type=click.Path(exists=True),
              default=None, help="指标定义文件（默认 config/metrics.yaml）")
def metrics_show(name: str, metrics_file: str | None) -> None:
    """查看单个指标的完整口径定义。"""
    _ensure_utf8_stdio()
    store, errors = _load_metrics_for_cli(metrics_file, None)
    for err in errors:
        console.print(f"[yellow]警告: {err}[/yellow]")
    m = store.get(name)
    if m is None:
        known = ", ".join(x.name for x in store.metrics) or "(无)"
        raise click.ClickException(f"指标 '{name}' 未定义。已知指标: {known}")
    console.print(f"[bold]{m.name}[/bold] ({m.display_name})")
    if m.aliases:
        console.print(f"别名: {', '.join(m.aliases)}")
    if m.description:
        console.print(f"口径: {m.description}")
    if m.is_ratio:
        console.print(f"类型: ratio = {m.numerator} / {m.denominator}")
    else:
        console.print(f"类型: additive = {m.expression} FROM {m.table}")
        console.print(f"时间列: {m.time_column or '(无)'}")
        console.print(f"允许维度: {', '.join(m.dimensions) or '(无)'}")
        for f in m.default_filters:
            console.print(f"恒定过滤: {f}")
    if m.unit:
        console.print(f"单位: {m.unit}")
    if m.owner:
        console.print(f"负责人: {m.owner}")


@metrics.command("validate")
@click.option("--file", "-f", "metrics_file", type=click.Path(exists=True),
              default=None, help="指标定义文件（默认 config/metrics.yaml）")
@click.option("--ddl", type=click.Path(exists=True), required=True,
              help="schema DDL 文件（表白名单），用于交叉校验")
def metrics_validate(metrics_file: str | None, ddl: str) -> None:
    """校验指标定义与 DDL 的一致性（CI 门禁：有错误时退出码 1）。"""
    _ensure_utf8_stdio()
    store, errors = _load_metrics_for_cli(metrics_file, ddl)
    if errors:
        for err in errors:
            console.print(f"[red]{err}[/red]")
        raise SystemExit(1)
    console.print(f"[green]校验通过：{len(store)} 个指标定义与 DDL 一致[/green]")


@metrics.command("sql")
@click.argument("name")
@click.option("--file", "-f", "metrics_file", type=click.Path(exists=True),
              default=None, help="指标定义文件（默认 config/metrics.yaml）")
@click.option("--ddl", type=click.Path(exists=True), required=True,
              help="schema DDL 文件（表白名单）")
@click.option("--dim", "-d", "dims", multiple=True, help="下钻维度（可多次）")
@click.option("--start", default=None, help="开始日期 YYYY-MM-DD / yyyyMMdd")
@click.option("--end", default=None, help="结束日期（含）")
@click.option("--max-partition", default=None, help="无时间范围时的最新分区值")
@click.option("--where", "-w", "filters", multiple=True, help="附加过滤条件（可多次）")
def metrics_sql(
    name: str, metrics_file: str | None, ddl: str, dims: tuple[str, ...],
    start: str | None, end: str | None, max_partition: str | None,
    filters: tuple[str, ...],
) -> None:
    """确定性展开指标 SQL（不执行）——同样的参数永远得到同一条 SQL。"""
    _ensure_utf8_stdio()
    from seatunnel_agent.agents.data.text2sql.metrics import (
        MetricError,
        build_metric_sql,
        parse_time_range,
    )

    store, errors = _load_metrics_for_cli(metrics_file, ddl)
    if errors:
        for err in errors:
            console.print(f"[red]{err}[/red]")
        raise SystemExit(1)
    m = store.get(name)
    if m is None:
        known = ", ".join(x.name for x in store.metrics) or "(无)"
        raise click.ClickException(f"指标 '{name}' 未定义。已知指标: {known}")

    from seatunnel_agent.agents.data.text2sql.schema import SchemaStore
    schema_store = SchemaStore.from_file(ddl)
    try:
        sql = build_metric_sql(
            m, store, schema_store,
            dimensions=list(dims),
            time_range=parse_time_range(start or "", end or ""),
            max_partition=max_partition,
            extra_filters=list(filters),
        )
    except MetricError as exc:
        raise click.ClickException(str(exc))
    click.echo(sql)


@click.group(name="t2s-examples")
def t2s_examples() -> None:
    """Chat BI few-shot 示例库：已验证的 问题→SQL 对（准确率飞轮）。"""


@t2s_examples.command("list")
@click.option("--file", "-f", "examples_file", type=click.Path(),
              default=None, help="示例库文件（默认 config/t2s_examples.json）")
def t2s_examples_list(examples_file: str | None) -> None:
    """列出全部示例。"""
    _ensure_utf8_stdio()
    from seatunnel_agent.agents.data.text2sql.examples import ExampleStore

    store = ExampleStore(examples_file)
    items = store.list()
    if not items:
        console.print("示例库为空（UI 里对查询结果点 👍 即可沉淀示例）")
        return
    from rich.table import Table
    table = Table(title=f"few-shot 示例库（{len(items)} 条）")
    for col in ("id", "问题", "来源", "SQL"):
        table.add_column(col)
    for it in items:
        table.add_row(
            it.get("id", ""), it.get("question", "")[:50],
            it.get("source", ""), it.get("sql", "").replace("\n", " ")[:60],
        )
    console.print(table)


@t2s_examples.command("add")
@click.option("--question", "-q", required=True, help="自然语言问题")
@click.option("--sql", "-s", required=True, help="对应的正确 SQL")
@click.option("--file", "-f", "examples_file", type=click.Path(),
              default=None, help="示例库文件（默认 config/t2s_examples.json）")
def t2s_examples_add(question: str, sql: str, examples_file: str | None) -> None:
    """手工添加一条验证示例。"""
    _ensure_utf8_stdio()
    from seatunnel_agent.agents.data.text2sql.examples import ExampleStore
    from seatunnel_agent.agents.data.text2sql.validator import extract_tables

    store = ExampleStore(examples_file)
    try:
        entry = store.add(question=question, sql=sql,
                          tables=extract_tables(sql), source="manual")
    except ValueError as exc:
        raise click.ClickException(str(exc))
    console.print(f"[green]已添加示例 {entry['id']}（现共 {len(store)} 条）[/green]")


@t2s_examples.command("rm")
@click.argument("example_id")
@click.option("--file", "-f", "examples_file", type=click.Path(),
              default=None, help="示例库文件（默认 config/t2s_examples.json）")
def t2s_examples_rm(example_id: str, examples_file: str | None) -> None:
    """按 id 删除一条示例。"""
    _ensure_utf8_stdio()
    from seatunnel_agent.agents.data.text2sql.examples import ExampleStore

    store = ExampleStore(examples_file)
    if store.remove(example_id):
        console.print(f"[green]已删除 {example_id}[/green]")
    else:
        raise click.ClickException(f"示例 '{example_id}' 不存在")


def register(cli) -> None:
    cli.add_command(t2s_bench)
    cli.add_command(t2s_index_values)
    cli.add_command(t2s_mcp)
    cli.add_command(t2s_sub)
    cli.add_command(t2s_cron)
    cli.add_command(t2s_eval)
    cli.add_command(dqc)
    cli.add_command(metrics)
    cli.add_command(t2s_examples)
