from __future__ import annotations

import sys

import click

from ..common.cli_common import console


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--sql", "-s", type=str, default=None, help="SQL text to analyze")
@click.option("--file", "-f", "sql_file", type=click.Path(exists=True), default=None,
              help="SQL file to analyze")
@click.option("--dir", "-D", "directory", type=click.Path(exists=True, file_okay=False),
              default=None, help="Analyze every *.sql file under a directory (recursive)")
@click.option("--dialect", "-d", type=click.Choice(["spark", "maxcompute", "hive"]),
              default="spark", show_default=True, help="SQL dialect")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--llm", "use_llm", is_flag=True,
              help="Also rewrite the SQL with the LLM (needs API key; default is static-only)")
@click.option("--fail-on", type=click.Choice(["high", "medium", "low"]), default=None,
              help="Exit 1 when findings at/above this severity exist (CI gate)")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
def skew(
    paths: tuple[str, ...],
    sql: str | None,
    sql_file: str | None,
    directory: str | None,
    dialect: str,
    lang: str,
    use_llm: bool,
    fail_on: str | None,
    fmt: str,
    output: str | None,
) -> None:
    """SQL 数据倾斜分析 — static skew-pattern scan, optional LLM rewrite.

    PATHS: optional *.sql files or directories (as passed by pre-commit)."""
    import json as _json
    from pathlib import Path

    from seatunnel_agent.agents.data.data_skew.history import default_history
    from seatunnel_agent.agents.data.data_skew.report import Severity, render_report

    from ..common.utils import collect_sql_files

    # ── collect analysis targets ──
    sources: list[tuple[str, str]] = []
    try:
        if sql:
            sources.append(("<inline>", sql))
        if sql_file:
            sources.append((sql_file, Path(sql_file).read_text(encoding="utf-8")))
        for raw in paths:
            p = Path(raw)
            if p.is_dir():
                for f in collect_sql_files(p):
                    sources.append((str(f), f.read_text(encoding="utf-8")))
            else:
                sources.append((str(p), p.read_text(encoding="utf-8")))
        if directory:
            for p in collect_sql_files(directory):
                sources.append((str(p), p.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError) as e:
        console.print(f"[red]收集分析目标失败:[/red] {e}")
        sys.exit(1)
    seen: set[str] = set()
    sources = [(label, text) for label, text in sources
               if not (label in seen or seen.add(label))]
    if not sources:
        raise click.UsageError("Provide SQL via --sql / --file / --dir or positional paths")

    # ── analyze ──
    history = default_history()
    results = []  # (label, SkewReport, markdown)
    for label, text in sources:
        if use_llm:
            from seatunnel_agent.agents.data.data_skew.agent import DataSkewAgent

            from ..common.config import load_settings
            try:
                settings = load_settings()
            except RuntimeError as e:
                raise click.ClickException(f"--llm 需要 LLM 配置: {e}")
            agent = DataSkewAgent(settings, dialect=dialect, lang=lang)
            res = agent.analyze(text, use_llm=True)
            rep, md = res.report, res.markdown
        else:
            from seatunnel_agent.agents.data.data_skew.agent import static_skew_report
            rep = static_skew_report(text, dialect, lang)
            md = render_report(rep, lang)
        history.log(text, rep, mode="llm" if use_llm else "static", source="cli")
        results.append((label, rep, md))

    # ── render ──
    if fmt == "json":
        payload = [
            {
                "file": label,
                "dialect": rep.dialect,
                "counts": {"high": len(rep.high), "medium": len(rep.medium),
                           "low": len(rep.low)},
                "findings": [f.to_dict() for f in rep.findings],
            }
            for label, rep, _ in results
        ]
        text_out = _json.dumps(payload, ensure_ascii=False, indent=2)
        print(text_out)
    else:
        parts = []
        for label, _, md in results:
            head = f"# 📄 {label}\n\n" if len(results) > 1 else ""
            parts.append(head + md)
        text_out = "\n\n---\n\n".join(parts)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    # ── CI gate ──
    if fail_on:
        rank = {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}
        threshold = {"low": 1, "medium": 2, "high": 3}[fail_on]
        worst = max((rank[f.severity] for _, rep, _ in results
                     for f in rep.findings), default=0)
        if worst >= threshold:
            msg = f"存在 {fail_on} 及以上级别的倾斜风险，检查未通过。"
            if fmt == "json":
                # keep stdout valid JSON for `... -F json | jq` pipelines
                print(msg, file=sys.stderr)
            else:
                console.print(f"\n[red]{msg}[/red]")
            sys.exit(1)


@click.command(name="skew-stats")
@click.option("--recent", "-n", type=int, default=20, help="显示最近 N 条")
def skew_stats(recent: int) -> None:
    """数据倾斜分析历史与统计 (logs/data_skew.jsonl)。"""
    from collections import Counter

    from seatunnel_agent.agents.data.data_skew.history import default_history

    records = default_history().recent(recent)
    if not records:
        console.print("[yellow]还没有数据倾斜分析记录。[/yellow]")
        return
    console.print("[bold]数据倾斜分析历史[/bold]")
    marks = {"high": "⛔", "medium": "⚠️", "clean": "✅"}
    for r in records:
        c = r.get("counts") or {}
        snippet = " ".join((r.get("sql") or "").split())[:60]
        console.print(
            f"  {r.get('timestamp', '')}  [{r.get('mode', '')}/{r.get('source', '')}] "
            f"{r.get('dialect', '')}  "
            f"⛔{c.get('high', 0)} ⚠️{c.get('medium', 0)} 🔵{c.get('low', 0)}  "
            f"{marks.get(r.get('verdict', ''), '')}  {snippet}")
    verdicts = Counter(r.get("verdict", "clean") for r in records)
    sources = Counter(r.get("source", "?") for r in records)
    dialects = Counter(r.get("dialect", "?") for r in records)
    console.print(
        f"\n[bold]汇总[/bold] 共 {len(records)} 次 · "
        f"高风险 {verdicts.get('high', 0)} 次 · "
        f"潜在 {verdicts.get('medium', 0)} 次 · 干净 {verdicts.get('clean', 0)} 次")
    console.print(
        "[bold]来源[/bold] " + " · ".join(f"{k}×{v}" for k, v in sources.most_common())
        + "   [bold]方言[/bold] "
        + " · ".join(f"{k}×{v}" for k, v in dialects.most_common()))
    llm_runs = sum(1 for r in records if r.get("mode") == "llm")
    optimized = sum(1 for r in records if r.get("optimized"))
    if llm_runs:
        console.print(f"[bold]LLM 改写[/bold] {llm_runs} 次,产出优化 SQL {optimized} 次")

    # ── split-key patrol trend: latest verdict + top-1 history per table ──
    h = default_history()
    tables = h.splitkey_tables()
    if tables:
        console.print("\n[bold]分片键巡检（每表最近趋势）[/bold]")
        v_marks = {"good": "✅", "suspect": "⚠️", "bad": "⛔",
                   "low_ndv": "⛔", "null": "⛔", "none": "⚠️"}
        for t in tables[:20]:
            trend = h.splitkey_trend(t, n=8)
            latest = (trend[-1].get("splitkey") or {}) if trend else {}
            v = str(latest.get("key_verdict") or "none")
            top1s = [
                f"{sk.get('top1_pct'):.0f}%"
                for rec in trend
                if (sk := rec.get("splitkey") or {}).get("top1_pct") is not None
            ]
            trail = (" · top1 " + " → ".join(top1s)) if top1s else ""
            console.print(
                f"  {v_marks.get(v, '')} {t}  key="
                f"{latest.get('partition_column') or '(none)'}  {v}"
                f"  ×{len(trend)} 次{trail}")


@click.command(name="skew-drift")
@click.argument("table", required=False)
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              help="报告语言")
@click.option("--webhook", "webhook_url", type=str, default=None,
              help="漂移时 POST JSON 到该 webhook（钉钉/企微/Slack 兼容）")
def skew_drift(table: str | None, lang: str, webhook_url: str | None) -> None:
    """分片键倾斜漂移检测 — 最新测量 vs 历史基线(离线,只读历史)。

    带 TABLE 看单表;不带则巡检所有有历史的表。
    """
    from seatunnel_agent.agents.data.data_skew.drift import (
        compute_drift,
        render_drift,
    )
    from seatunnel_agent.agents.data.data_skew.history import default_history
    from seatunnel_agent.agents.data.data_skew.i18n import dsk as _dsk

    history = default_history()
    tables = [table] if table else history.splitkey_tables()
    if not tables:
        console.print(_dsk(lang, "drf_none"))
        return
    drifted = []
    for t in tables:
        result = compute_drift(t, history.splitkey_trend(t, n=50))
        console.print(render_drift(result, lang))
        history.log_drift(t, result.verdict,
                          [d.metric for d in result.drifts], source="cli")
        if result.verdict == "drift":
            drifted.append((t, result))
    if webhook_url and drifted:
        from seatunnel_agent.agents.data.data_skew.notify import post_webhook
        ok, msg = post_webhook(webhook_url, {
            "source": "seatunnel-agent", "kind": "skew_drift",
            "tables": [t for t, _ in drifted],
            "text": "\n\n".join(render_drift(r, lang) for _, r in drifted)})
        console.print(f"[dim]webhook: {'ok' if ok else 'failed'} ({msg})[/dim]")


@click.command(name="skew-splitkey")
@click.argument("conf_path", type=click.Path(exists=True))
@click.option("--ds", "ds_type",
              type=click.Choice(["hive", "sparksql", "mysql", "postgresql",
                                 "sqlite", "clickhouse", "doris"]),
              default="mysql", show_default=True, help="数据源类型")
@click.option("--db", type=str, default=None,
              help="host:port/database（缺省时读 .env 中该数据源的配置）")
@click.option("--db-user", type=str, default=None, help="数据库用户名")
@click.option("--db-password", type=str, default=None, help="数据库密码")
@click.option("--sample", type=int, default=0, show_default=True,
              help="探查采样百分比（0 = 全量；仅 Hive/Spark/PG 生效）")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save report to file")
@click.option("--fail", "fail_flag", is_flag=True,
              help="已配置的 partition_column 实测倾斜/低基数/NULL 过多时退出码 1（CI 门禁）")
@click.option("--apply", "apply_flag", is_flag=True,
              help="把实测推荐的分片键写回配置文件（原文件备份为 .bak），随后重新体检即完成闭环")
@click.option("--webhook", "webhook_url", type=str, default=None,
              help="发现倾斜键/解析失败时把巡检摘要 POST 到该 webhook（目录模式常配 cron 使用）")
def skew_splitkey(
    conf_path: str,
    ds_type: str,
    db: str | None,
    db_user: str | None,
    db_password: str | None,
    sample: int,
    lang: str,
    output: str | None,
    fail_flag: bool,
    apply_flag: bool,
    webhook_url: str | None,
) -> None:
    """SeaTunnel 分片键体检 — 连库实测作业配置的 partition_column 分布。

    CONF_PATH: SeaTunnel 作业配置文件（HOCON），或一个配置目录——目录模式
    递归扫描 *.conf/*.config/*.hocon/*.json 逐个体检并输出巡检汇总表。"""
    import re as _re
    from pathlib import Path

    from seatunnel_agent.agents.data.data_skew.history import default_history
    from seatunnel_agent.agents.data.data_skew.i18n import dsk as _dsk
    from seatunnel_agent.agents.data.data_skew.probe import effective_sample_pct
    from seatunnel_agent.agents.data.data_skew.splitkey import (
        SplitKeyError,
        apply_split_key,
        batch_counts,
        pick_best_key,
        render_splitkey_batch,
        render_splitkey_multi,
        run_split_key_batch,
        run_split_key_multi,
        scan_config_files,
        sink_key_section,
        splitkey_metrics,
    )
    from seatunnel_agent.agents.data.text2sql.executor.base import (
        DatabaseConfig,
        config_from_env,
        create_executor,
    )

    if db:
        m = _re.fullmatch(r"([\w.\-]+):(\d+)/([\w.\-]+)", db.strip())
        if not m:
            raise click.UsageError("--db 格式应为 host:port/database")
        cfg = DatabaseConfig(
            ds_type=ds_type,
            host=m.group(1), port=int(m.group(2)), database=m.group(3),
            username=db_user, password=db_password,
        )
    else:
        cfg = config_from_env(ds_type)
        if cfg is None:
            raise click.ClickException(
                f".env 中未找到 {ds_type} 的连接配置——请配置 .env 或用 --db 指定")

    pct = effective_sample_pct(ds_type, sample)
    try:
        executor = create_executor(cfg)
    except Exception as exc:
        raise click.ClickException(f"连接失败: {exc}")
    history = default_history()

    def _notify(md_text: str, counts: dict) -> None:
        """POST the patrol summary when the webhook is set and something
        is wrong (a healthy patrol stays silent)."""
        if not webhook_url or not (counts.get("bad") or counts.get("errors")):
            return
        from seatunnel_agent.agents.data.data_skew.notify import post_webhook
        ok, msg = post_webhook(webhook_url, {
            "source": "seatunnel-agent", "kind": "splitkey_patrol",
            "counts": counts, "text": md_text})
        console.print(f"[dim]webhook: {'ok' if ok else 'failed'} ({msg})[/dim]")

    conf_dir = Path(conf_path)
    if conf_dir.is_dir():
        # ── directory patrol: every config, one summary table ──
        if apply_flag:
            raise click.UsageError(
                "--apply 仅支持单个配置文件——目录巡检后请逐个文件应用")
        files = scan_config_files(str(conf_dir))
        if not files:
            raise click.ClickException(
                "目录下未找到 *.conf/*.config/*.hocon/*.json 配置文件")
        items = run_split_key_batch(executor, files, ds_type=ds_type,
                                    sample_pct=pct)
        for it in items:
            for spec, configured, candidates in it.results:
                history.log_splitkey(
                    spec.table, spec.partition_column,
                    configured.verdict(spec.tasks) if configured else "none",
                    candidates=len(candidates), source="cli",
                    **splitkey_metrics(configured))
        md = render_splitkey_batch(items, lang, sample_pct=pct)
        console.print(md)
        if output:
            Path(output).write_text(md, encoding="utf-8")
            console.print(f"[dim]报告已保存: {output}[/dim]")
        # drift tail (directory mode): only the drifted tables, one line each
        from seatunnel_agent.agents.data.data_skew.drift import (
            compute_drift,
            render_drift,
        )
        seen: list[tuple[str, str]] = []
        for it in items:
            for spec, _, _ in it.results:
                tk = (spec.table, spec.partition_column)
                if tk not in seen:
                    seen.append(tk)
        for t, col in seen:
            d = compute_drift(t, history.splitkey_trend(t, n=50), column=col)
            if d.verdict == "drift":
                console.print(render_drift(d, lang))

        c = batch_counts(items)
        _notify(md, c)
        if fail_flag and (c["bad"] or c["errors"]):
            console.print(f"\n[red]{c['bad']} 个倾斜键 / {c['errors']} 个"
                          f"解析失败，巡检未通过。[/red]")
            sys.exit(1)
        return

    conf_text = conf_dir.read_text(encoding="utf-8", errors="replace")
    try:
        results, total = run_split_key_multi(
            executor, conf_text, ds_type=ds_type, sample_pct=pct)
    except SplitKeyError as exc:
        raise click.ClickException(_dsk(lang, exc.key).format(err=exc.arg))
    except Exception as exc:
        raise click.ClickException(f"体检失败: {exc}")

    # previous checks of the same tables BEFORE logging this run — feeds
    # each source's re-check comparison line (did the last fix land?)
    previous_by_table = {spec.table: prev for spec, _, _ in results
                         if (prev := history.last_splitkey(spec.table))}
    verdicts: list[str] = []
    for spec, configured, candidates in results:
        key_verdict = configured.verdict(spec.tasks) if configured else "none"
        verdicts.append(key_verdict)
        history.log_splitkey(
            spec.table, spec.partition_column, key_verdict,
            candidates=len(candidates), source="cli",
            **splitkey_metrics(configured))

    md = render_splitkey_multi(results, lang, sample_pct=pct, total=total,
                               previous_by_table=previous_by_table)
    snk = sink_key_section(executor, conf_text, ds_type=ds_type,
                           sample_pct=pct, lang=lang)
    if snk:
        md = md + "\n" + snk
    console.print(md)
    if output:
        Path(output).write_text(md, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")
    # drift tail: the measurement just logged vs the table's baseline
    from seatunnel_agent.agents.data.data_skew.drift import (
        compute_drift,
        render_drift,
    )
    for spec, _, _ in results:
        d = compute_drift(spec.table, history.splitkey_trend(spec.table, n=50),
                          column=spec.partition_column)
        console.print(render_drift(d, lang))

    _notify(md, {"bad": sum(1 for v in verdicts
                            if v in ("bad", "low_ndv", "null")), "errors": 0})

    if apply_flag:
        if total > 1:
            # a text-level edit could anchor on the wrong source block
            raise click.ClickException(
                _dsk(lang, "spk_apply_multi").format(n=total))
        spec, configured, candidates = results[0]
        best = pick_best_key(spec, configured, candidates)
        if best is None or best.column == spec.partition_column:
            console.print(_dsk(lang, "spk_apply_none"))
        else:
            try:
                new_text = apply_split_key(
                    conf_text, spec, best.column,
                    partition_num=max(spec.partition_num, spec.tasks))
            except SplitKeyError as exc:
                raise click.ClickException(
                    _dsk(lang, exc.key).format(err=exc.arg))
            bak = conf_path + ".bak"
            Path(bak).write_text(conf_text, encoding="utf-8")
            Path(conf_path).write_text(new_text, encoding="utf-8")
            console.print(_dsk(lang, "spk_apply_done").format(
                opt=spec.split_option, col=best.column, bak=bak))

    bad = [v for v in verdicts if v in ("bad", "low_ndv", "null")]
    if fail_flag and bad:
        console.print(f"\n[red]partition_column 实测判定为 {'/'.join(bad)}，检查未通过。[/red]")
        sys.exit(1)


@click.command(name="skew-runtime")
@click.argument("eventlog", required=False,
                type=click.Path(exists=True))
@click.option("--history", "history_url", type=str, default=None,
              help="Spark History Server 地址（如 http://host:18080），与 --app 搭配")
@click.option("--app", "app_id", type=str, default=None,
              help="History Server 上的 application ID")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
@click.option("--fail", "fail_flag", is_flag=True,
              help="存在确认倾斜的 stage 时退出码 1（CI 门禁）")
def skew_runtime(
    eventlog: str | None,
    history_url: str | None,
    app_id: str | None,
    lang: str,
    output: str | None,
    fail_flag: bool,
) -> None:
    """运行时倾斜诊断 — 从 Spark 任务指标定位拖尾 stage。

    EVENTLOG: Spark event log 文件 / .gz / 滚动目录（离线），
    或改用 --history + --app 走 History Server REST API（在线）。"""
    from pathlib import Path

    from seatunnel_agent.agents.data.data_skew.history import default_history
    from seatunnel_agent.agents.data.data_skew.i18n import dsk as _dsk
    from seatunnel_agent.agents.data.data_skew.runtime import (
        RuntimeSkewError,
        analyze_history_server,
        parse_eventlog,
        render_runtime_section,
    )

    if bool(eventlog) == bool(history_url or app_id):
        raise click.UsageError(
            "指定 EVENTLOG 文件，或 --history 加 --app，二选一")
    try:
        if eventlog:
            stages, label = parse_eventlog(eventlog)
        else:
            if not (history_url and app_id):
                raise click.UsageError("--history 与 --app 需同时提供")
            stages, label = analyze_history_server(history_url, app_id)
    except RuntimeSkewError as exc:
        raise click.ClickException(_dsk(lang, exc.key).format(err=exc.arg))

    confirmed = sum(1 for s in stages if s.verdict() == "confirmed")
    suspect = sum(1 for s in stages if s.verdict() == "suspect")
    default_history().log_runtime(label, len(stages), confirmed, suspect,
                                  source="cli")

    md = render_runtime_section(stages, lang, source_label=label)
    console.print(md)
    if output:
        Path(output).write_text(md, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")
    if fail_flag and confirmed:
        console.print(f"\n[red]{confirmed} 个 stage 确认倾斜，检查未通过。[/red]")
        sys.exit(1)


@click.command(name="skew-mcp")
@click.option("--dialect", "-d", type=click.Choice(["spark", "maxcompute", "hive"]),
              default="spark", show_default=True, help="Default SQL dialect")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Default report language")
def skew_mcp(dialect: str, lang: str) -> None:
    """以 MCP server（stdio）暴露数据倾斜静态分析，供 Claude Desktop 等 MCP 客户端调用。"""
    from seatunnel_agent.agents.data.data_skew.mcp_server import create_mcp_server

    try:
        server = create_mcp_server(default_dialect=dialect, default_lang=lang)
    except RuntimeError as exc:
        raise click.ClickException(str(exc))
    server.run()


def register(cli) -> None:
    cli.add_command(skew)
    cli.add_command(skew_stats)
    cli.add_command(skew_drift)
    cli.add_command(skew_splitkey)
    cli.add_command(skew_runtime)
    cli.add_command(skew_mcp)
