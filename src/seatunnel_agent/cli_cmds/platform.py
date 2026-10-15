from __future__ import annotations

import os
import sys

import click

from ..cli import console


@click.command(name="mcp")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Default report language")
@click.option("--sql-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="启用血缘工具：从目录下的 *.sql 构建血缘图（递归）")
@click.option("--sql-dialect", type=click.Choice(
                  ["hive", "spark", "flink", "maxcompute", "mysql",
                   "postgresql", "clickhouse", "doris", "starrocks", "sqlite"]),
              default="hive", show_default=True,
              help="解析 --sql-dir 脚本用的 SQL 方言")
@click.option("--seatunnel-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="启用血缘工具：从 SeaTunnel 配置目录构建 source→sink 血缘")
@click.option("--hive", "use_hive", is_flag=True,
              help="启用血缘工具：从 Hive 元数据血缘表构建（需 .env 配置）")
@click.option("--meta-table", type=str, default=None,
              help="血缘元数据表名（默认 zz.dwm_meta_table_lineage_df）")
@click.option("--partition", type=str, default=None,
              help="指定 pt 分区（默认自动取最新分区）")
@click.option("--connections", type=str, default=None,
              help="数据库工具可用的连接名白名单（逗号分隔；默认全部已保存连接）")
@click.option("--no-db", "no_db", is_flag=True,
              help="纯静态模式：只暴露 6 个静态分析工具，不加载任何数据库工具")
def mcp_toolbox_cmd(
    lang: str,
    sql_dir: str | None,
    sql_dialect: str,
    seatunnel_dir: str | None,
    use_hive: bool,
    meta_table: str | None,
    partition: str | None,
    connections: str | None,
    no_db: bool,
) -> None:
    """统一 MCP 工具箱（stdio）：SQL 审查/方言翻译/倾斜分析/变更影响/配置迁移
    + 已保存连接上的表结构浏览、只读查询与跨库比对。全部确定性实现，不调用
    LLM。血缘工具在给出 --sql-dir / --seatunnel-dir / --hive 之一时加载。"""
    from ..mcp_toolbox import create_mcp_server

    allow = ([n.strip() for n in connections.split(",") if n.strip()]
             if connections else None)
    try:
        server = create_mcp_server(
            default_lang=lang, sql_dir=sql_dir, seatunnel_dir=seatunnel_dir,
            use_hive=use_hive, meta_table=meta_table, partition=partition,
            sql_dialect=sql_dialect, connections=allow, include_db=not no_db,
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc))
    server.run()


@click.command(name="mcp-stats")
@click.option("--recent", "-n", type=int, default=20, help="显示最近 N 条")
def mcp_stats(recent: int) -> None:
    """MCP 工具箱调用审计与统计 (logs/mcp_toolbox.jsonl)。"""
    import json as _json
    from collections import Counter, defaultdict

    from ..mcp_toolbox import _audit_file

    path = _audit_file()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        console.print("[yellow]还没有 MCP 工具调用记录。[/yellow]")
        return
    records = []
    for line in lines:
        try:
            records.append(_json.loads(line))
        except ValueError:
            continue
    if not records:
        console.print("[yellow]还没有 MCP 工具调用记录。[/yellow]")
        return
    console.print("[bold]最近调用[/bold]")
    for r in records[-recent:]:
        mark = "✅" if r.get("ok") else "⛔"
        console.print(
            f"  {r.get('timestamp', '')}  {mark} {r.get('tool', ''):<24} "
            f"{r.get('elapsed_ms', 0):>6} ms  {str(r.get('args', ''))[:60]}")
    by_tool: dict[str, list] = defaultdict(list)
    for r in records:
        by_tool[r.get("tool", "?")].append(r)
    ok_total = sum(1 for r in records if r.get("ok"))
    console.print(
        f"\n[bold]汇总[/bold] 共 {len(records)} 次调用 · 成功 {ok_total} · "
        f"失败 {len(records) - ok_total}")
    rows = sorted(by_tool.items(), key=lambda kv: -len(kv[1]))
    for tool, rs in rows:
        ok = sum(1 for r in rs if r.get("ok"))
        avg = sum(int(r.get("elapsed_ms", 0)) for r in rs) // max(len(rs), 1)
        console.print(f"  {tool:<26} {len(rs):>4} 次 · 成功率 "
                      f"{100 * ok // max(len(rs), 1):>3}% · 平均 {avg} ms")
    fails = Counter(r.get("tool", "?") for r in records if not r.get("ok"))
    if fails:
        top = " · ".join(f"{t}×{c}" for t, c in fails.most_common(5))
        console.print(f"[bold]失败集中在[/bold] {top}")


@click.command(context_settings={"ignore_unknown_options": True})
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def uitest(args: tuple[str, ...]) -> None:
    """UI 测试 Agent（run / list / compare / trend，参数原样转发）。

    Examples: seatunnel-agent uitest run --suite smoke --no-llm
    """
    from ..ui_testing.__main__ import main as uitest_main
    sys.exit(uitest_main(list(args) or ["run", "--suite", "smoke"]))


@click.command()
@click.option("--clear", "clear_", is_flag=True,
              help="清除界面保存的 LLM 配置覆盖（恢复 .env）")
@click.option("--usage", "usage_", is_flag=True,
              help="显示近 30 天 LLM token 用量（按模型汇总；读取当前目录的 "
                   "logs/llm_usage.jsonl，请在项目根目录运行）")
def settings(clear_: bool, usage_: bool) -> None:
    """查看当前生效的 LLM 配置（界面覆盖 or .env），或清除界面覆盖。"""
    from dotenv import load_dotenv

    from .. import settings_store

    load_dotenv()
    settings_store.apply_to_env()
    if clear_:
        settings_store.clear()
        console.print("[green]OK[/green] 已清除界面覆盖，恢复 .env 配置")
        return
    if usage_:
        from ..llm_usage import format_markdown
        console.print(format_markdown("zh"))
        return
    src = ("界面设置（覆盖 .env） — " + str(settings_store.store_path())
           if settings_store.has_saved() else ".env / 环境变量")
    from ..config import env_api_key
    key = env_api_key()
    console.print(f"来源: {src}")
    console.print(f"LLM_PROVIDER = {os.getenv('LLM_PROVIDER', 'anthropic')}")
    console.print(f"MODEL_NAME   = {os.getenv('MODEL_NAME', 'claude-opus-5')}")
    console.print(f"LLM_BASE_URL = {os.getenv('LLM_BASE_URL', '') or '(未设置)'}")
    console.print(
        f"API_KEY      = {settings_store.mask_secret(key) or '(未设置)'}")


@click.command()
@click.option("--days", default=30, show_default=True,
              type=click.IntRange(1, 36500), help="统计时间窗(天)")
@click.option("--budget", type=float, default=None,
              help="预算上限(USD),配合 --fail-on budget")
@click.option("--usage-path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="用量日志路径(默认 logs/llm_usage.jsonl)")
@click.option("--pricing", type=click.Path(exists=True, dir_okay=False),
              default=None, help="价格覆盖 YAML(默认 ~/.seatunnel-agent/pricing.yaml)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["budget"]), default=None,
              help="CI gate: budget=时间窗内成本超过 --budget 时退出 1")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
@click.option("--notify", "do_notify", is_flag=True,
              help="NOTIFY_WEBHOOK_URL webhook alert on anomaly/over-budget")
def llmcost(
    days: int,
    budget: float | None,
    usage_path: str | None,
    pricing: str | None,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
    do_notify: bool,
) -> None:
    """LLM 成本观测 — 按模型/按天/按 agent 汇总调用成本,异常日标记。

    读取全平台 LLM 调用日志并按近似价格表计价(可用 YAML 覆盖);
    不调用 LLM、不连数据库。"""
    import json as _json
    from pathlib import Path

    from ..llm_cost import check_budget, render_markdown, summarize_cost

    if fail_on == "budget" and budget is None:
        raise click.UsageError("--fail-on budget 需要同时提供 --budget")

    try:
        summary = summarize_cost(days, usage_file=usage_path,
                                 pricing_override=pricing)
    except ValueError as exc:  # malformed pricing override
        console.print(f"[red]{exc}[/red]")
        sys.exit(2)

    if fmt == "json":
        text_out = _json.dumps(summary, ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_markdown(summary, lang)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    if do_notify:
        from ..notify import send as notify_send
        over = budget is not None and check_budget(summary, budget)
        if summary["anomalies"] or over:
            parts = []
            if over:
                parts.append(f"over budget: ${summary['total']['cost_usd']}"
                             f" / ${budget}")
            parts += [f"anomaly {a['day']}: ${a['cost_usd']}"
                      for a in summary["anomalies"][:5]]
            notify_send("LLM cost alert", "; ".join(parts))

    if fail_on == "budget" and check_budget(summary, budget):
        msg = (f"成本 ${summary['total']['cost_usd']} 超过预算 ${budget},"
               "检查未通过。")
        if fmt == "json":
            print(msg, file=sys.stderr)
        else:
            console.print(f"\n[red]{msg}[/red]")
        sys.exit(1)


@click.command()
@click.argument("prompt")
@click.option("--profile", "-p", "profiles", multiple=True,
              help="模型档案名(可重复;默认当前生效配置 \"(active)\")")
@click.option("--system", "-S", default=None, help="自定义 system prompt")
@click.option("--parallel", is_flag=True, help="并行调用各档案")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
def promptlab(
    prompt: str,
    profiles: tuple[str, ...],
    system: str | None,
    parallel: bool,
    lang: str,
    fmt: str,
    output: str | None,
) -> None:
    """Prompt 实验室 — 同一 Prompt 在多个模型档案上并排对比。

    档案来自 /settings 页保存的 provider profiles;"(active)" 表示当前
    生效配置。全部档案失败时退出 1。"""
    import json as _json
    from pathlib import Path

    from dotenv import load_dotenv

    from .. import settings_store
    from ..prompt_lab import ACTIVE, render_matrix_markdown, run_matrix

    load_dotenv()
    settings_store.apply_to_env()

    names = list(profiles) or [ACTIVE]
    result = run_matrix(prompt, system=system, profiles=names,
                        parallel=parallel)

    if fmt == "json":
        text_out = _json.dumps([c.to_dict() for c in result.cells],
                               ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_matrix_markdown(result, lang)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    if result.all_failed:
        msg = "所有档案调用失败。"
        if fmt == "json":
            print(msg, file=sys.stderr)
        else:
            console.print(f"\n[red]{msg}[/red]")
        sys.exit(1)


@click.command()
@click.argument("suite_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--judge", is_flag=True,
              help="同时运行 judge 评分(仅参考,不进入门禁)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--fail-on", type=click.Choice(["fail", "regression"]),
              default=None,
              help="CI gate: fail=有 case 未通过; regression=相比上次运行回归")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
@click.option("--notify", "do_notify", is_flag=True,
              help="NOTIFY_WEBHOOK_URL webhook alert on regression/failures")
def llmeval(
    suite_file: str,
    judge: bool,
    lang: str,
    fail_on: str | None,
    fmt: str,
    output: str | None,
    do_notify: bool,
) -> None:
    """LLM 评测 — 对平台 LLM 功能跑黄金用例集,自动打分 + 回归门禁。

    SUITE_FILE: YAML 套件(见 examples/llmeval_demo/)。确定性检查决定
    通过与否;--judge 的 LLM 评分仅作参考。"""
    import json as _json
    from pathlib import Path

    from dotenv import load_dotenv

    from .. import settings_store
    from ..llm_eval import RunLogger, compare, load_suite, render_markdown, run_suite

    load_dotenv()
    settings_store.apply_to_env()

    try:
        suite = load_suite(suite_file)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(2)

    baseline = RunLogger().last_run(suite.name)  # BEFORE run_suite logs its own
    try:
        result = run_suite(suite, judge=judge)
    except RuntimeError as exc:  # no API key configured etc.
        console.print(f"[red]{exc}[/red]")
        sys.exit(2)
    regression = compare(result, baseline)

    if fmt == "json":
        payload = {"result": result.to_dict(), "regression": regression}
        text_out = _json.dumps(payload, ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_markdown(result, lang, regression)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")

    if do_notify and (result.failed_cases or regression["regressed"]):
        from ..notify import send as notify_send
        notify_send(
            f"LLM eval alert: {suite.name}",
            f"score {result.score:.0%}; failed: "
            f"{', '.join(result.failed_cases) or '-'}; regressed: "
            f"{', '.join(regression['regressed_cases']) or '-'}")

    if fail_on:
        hit = (bool(result.failed_cases) if fail_on == "fail"
               else regression["regressed"])
        if hit:
            msg = ("存在未通过的 case,检查未通过。" if fail_on == "fail"
                   else "相比上次运行存在回归,检查未通过。")
            if fmt == "json":
                print(msg, file=sys.stderr)
            else:
                console.print(f"\n[red]{msg}[/red]")
            sys.exit(1)


@click.command()
@click.argument("request")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Reply language")
@click.option("--max-steps", default=5, show_default=True,
              type=click.IntRange(1, 10), help="工具调用轮数上限")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
def orchestrate(
    request: str,
    lang: str,
    max_steps: int,
    fmt: str,
    output: str | None,
) -> None:
    """智能编排 — 一句话需求,LLM 自动路由到合适的 agent 并串联多步。

    REQUEST: 自然语言需求(SQL/配置/DDL 直接写在里面)。未配置 LLM 时
    退化为关键词推荐(只建议不执行,退出码 0);LLM 调用失败退出 1。"""
    import json as _json
    from pathlib import Path

    from dotenv import load_dotenv

    from .. import settings_store
    from ..config import load_settings
    from ..orchestrator import (
        Orchestrator, build_catalog, render_markdown, render_suggestions,
        suggest,
    )

    load_dotenv()
    settings_store.apply_to_env()

    try:
        settings = load_settings()
    except RuntimeError:
        catalog = build_catalog(default_lang=lang)
        text_out = render_suggestions(suggest(request, catalog), lang)
        if fmt == "json":
            payload = {"reply": text_out, "steps": [],
                       "suggested_only": True}
            text_out = _json.dumps(payload, ensure_ascii=False, indent=2)
            print(text_out)
        else:
            console.print(text_out, markup=False)
        if output:
            Path(output).write_text(text_out, encoding="utf-8")
        return

    try:
        result = Orchestrator(settings, lang=lang,
                              max_steps=max_steps).run(request)
    except Exception as exc:  # noqa: BLE001 — LLM/provider errors
        console.print(f"[red]编排失败: {type(exc).__name__}: {exc}[/red]")
        sys.exit(1)

    if fmt == "json":
        text_out = _json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_markdown(result, lang)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")


@click.command()
@click.option("--repo", default=".", show_default=True,
              type=click.Path(exists=True, file_okay=False),
              help="git 仓库路径")
@click.option("--from", "since", default=None,
              help="起始 ref(默认上一个 tag;无 tag 则全部历史)")
@click.option("--to", "until", default="HEAD", show_default=True,
              help="结束 ref")
@click.option("--log-file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="改读提交记录文件(每行 sha<TAB>subject),不跑 git")
@click.option("--version", "-V", "current_version", default=None,
              help="当前版本(默认读 pyproject.toml)")
@click.option("--polish", is_flag=True, help="LLM 润色(需 API key;失败则回退确定性结果)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format (json for machines/CI)")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
def relnotes(
    repo: str,
    since: str | None,
    until: str,
    log_file: str | None,
    current_version: str | None,
    polish: bool,
    lang: str,
    fmt: str,
    output: str | None,
) -> None:
    """发布助手 — conventional commits 分组 changelog + 语义化版本建议。

    默认读取 --repo 自上个 tag 以来的提交;--log-file 可离线输入。"""
    import json as _json
    from pathlib import Path

    from ..release_notes import (
        build_notes, collect_git_log, current_version_from_pyproject,
        polish_markdown, render_markdown,
    )

    if log_file:
        log_text = Path(log_file).read_text(encoding="utf-8")
    else:
        try:
            log_text = collect_git_log(repo, since=since, until=until)
        except RuntimeError as exc:
            console.print(f"[red]git 读取失败: {exc}[/red]")
            sys.exit(2)
    if current_version is None:
        current_version = current_version_from_pyproject(repo)

    notes = build_notes(log_text, current_version)
    if fmt == "json":
        text_out = _json.dumps(notes.to_dict(), ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_markdown(notes, lang)
        if polish:
            from dotenv import load_dotenv

            from .. import settings_store
            load_dotenv()
            settings_store.apply_to_env()
            text_out = polish_markdown(text_out, lang)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
        console.print(f"[dim]报告已保存: {output}[/dim]")


@click.command()
@click.option("--port", "-p", default=9000, show_default=True, type=int,
              help="Webhook 服务端口")
@click.option("--host", "-h", default="127.0.0.1", show_default=True,
              help="绑定地址(公网回调需 0.0.0.0 或反代)")
@click.option("--secret-env", default="WEBHOOK_SECRET", show_default=True,
              help="读取 webhook secret 的环境变量名(未设置则不校验签名)")
def bot(port: int, host: str, secret_env: str) -> None:
    """GitHub Bot — PR opened/updated 时自动跑凭证扫描 + SQL 静态审查并回贴评论。

    需要:仓库 webhook 指向 http://<host>:<port>/webhook(事件选 Pull
    requests),GITHUB_TOKEN 环境变量用于拉 diff 与发评论。"""
    import os as _os

    try:
        import uvicorn
    except ImportError:
        console.print("[red]需要 uvicorn(随 gradio 安装):pip install uvicorn[/red]")
        sys.exit(1)

    from ..bot import create_bot_app

    secret = _os.getenv(secret_env, "")
    if not secret:
        console.print(f"[yellow]警告: 环境变量 {secret_env} 未设置,"
                      "将不校验 webhook 签名(仅限内网测试)[/yellow]")
    if not _os.getenv("GITHUB_TOKEN"):
        console.print("[yellow]警告: GITHUB_TOKEN 未设置,"
                      "私有仓库拉 diff / 发评论会失败[/yellow]")
    console.print(f"[green]Bot webhook: http://{host}:{port}/webhook[/green]")
    uvicorn.run(create_bot_app(secret=secret), host=host, port=port)


@click.command()
@click.argument("question")
@click.option("--docs", default="docs", show_default=True,
              help="额外索引的 markdown 文档目录(连接器文档始终内置)")
@click.option("-k", "top_k", default=4, show_default=True,
              type=click.IntRange(1, 10), help="检索片段数")
@click.option("--llm", "use_llm", is_flag=True,
              help="LLM 综合作答(需 API key;失败回退检索片段)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Answer language")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Output format")
def docqa(
    question: str,
    docs: str,
    top_k: int,
    use_llm: bool,
    lang: str,
    fmt: str,
) -> None:
    """文档问答 — 离线 BM25 检索 SeaTunnel 连接器与项目文档,带来源引用。"""
    import json as _json

    from ..doc_qa import answer, get_index

    if use_llm:
        from dotenv import load_dotenv

        from .. import settings_store
        load_dotenv()
        settings_store.apply_to_env()
    result = answer(question, get_index(docs), k=top_k, lang=lang,
                    use_llm=use_llm)
    if fmt == "json":
        print(_json.dumps(result, ensure_ascii=False, indent=2))
    else:
        console.print(result["markdown"], markup=False)


@click.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--tests", "-t", default="", help="pytest 选择器(留空跑全部)")
@click.option("--instruction", "-i", default="", help="给 agent 的补充说明")
@click.option("--max-steps", default=12, show_default=True,
              type=click.IntRange(2, 30), help="工具调用步数上限")
@click.option("--in-place", is_flag=True,
              help="直接修改目标目录(默认在 git worktree 隔离执行)")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save report to file")
def codefix(
    path: str,
    tests: str,
    instruction: str,
    max_steps: int,
    in_place: bool,
    lang: str,
    fmt: str,
    output: str | None,
) -> None:
    """测试自愈 Agent — 跑测试→读码→打补丁→复跑,直到通过。

    默认在新建 git worktree 中执行,原工作区不动;最终以确定性复跑验收,
    测试仍不过则退出码 1。"""
    import json as _json
    from pathlib import Path

    from dotenv import load_dotenv

    from .. import settings_store
    from ..code_fix import fix, render_markdown
    from ..config import load_settings

    load_dotenv()
    settings_store.apply_to_env()
    try:
        settings = load_settings()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(2)

    def on_step(step):
        mark = "⚠️ " if step.error else ""
        console.print(f"[dim]🔧 {mark}{step.tool} · {step.elapsed_ms} ms[/dim]")

    try:
        result = fix(path, settings, tests=tests, instruction=instruction,
                     max_steps=max_steps, in_place=in_place, on_step=on_step)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(2)

    if fmt == "json":
        text_out = _json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        print(text_out)
    else:
        text_out = render_markdown(result, lang)
        console.print(text_out, markup=False)
    if output:
        Path(output).write_text(text_out, encoding="utf-8")
    if not result.success:
        sys.exit(1)


@click.command()
@click.option("--title", "-t", required=True, help="Issue 标题")
@click.option("--body", "-b", default="", help="Issue 正文")
@click.option("--issues-file", type=click.Path(exists=True, dir_okay=False),
              default=None,
              help="历史 issue JSONL(查重语料;默认内置 demo)")
@click.option("--repo", default=".", show_default=True,
              type=click.Path(exists=True, file_okay=False),
              help="代码检索用的仓库路径")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
@click.option("--format", "-F", "fmt", type=click.Choice(["markdown", "json"]),
              default="markdown", help="Report format")
def triage_cmd(
    title: str,
    body: str,
    issues_file: str | None,
    repo: str,
    lang: str,
    fmt: str,
) -> None:
    """Issue 分诊 Agent — 查重、定位、打标签并草拟回复(需 API key)。"""
    import json as _json
    from pathlib import Path

    from dotenv import load_dotenv

    from .. import settings_store
    from ..config import load_settings
    from ..issue_triage import load_issues, render_markdown, triage

    load_dotenv()
    settings_store.apply_to_env()
    try:
        settings = load_settings()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(2)

    if issues_file is None:
        demo = Path("examples/triage_demo/issues.jsonl")
        issues = load_issues(demo) if demo.is_file() else []
    else:
        issues = load_issues(issues_file)
    result = triage(title, body, settings, issues=issues, repo_dir=repo)
    if fmt == "json":
        print(_json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        console.print(render_markdown(result, lang), markup=False)


# click command name without the _cmd suffix
triage_cmd.name = "triage"


@click.command()
@click.argument("complaint", required=False, default="")
@click.option("--lang", type=click.Choice(["zh", "en"]), default="zh",
              show_default=True, help="Report language")
def doctor(complaint: str, lang: str) -> None:
    """环境医生 — 描述症状,agent 只读检查端口/依赖/配置/日志并开出修复命令。

    不带参数或未配置 API key 时输出确定性全量体检。"""
    from dotenv import load_dotenv

    from .. import settings_store
    from ..config import load_settings
    from ..doctor import diagnose

    load_dotenv()
    settings_store.apply_to_env()
    settings = None
    if complaint.strip():
        try:
            settings = load_settings()
        except RuntimeError:
            settings = None

    def on_step(step):
        console.print(f"[dim]🔧 {step.tool} · {step.elapsed_ms} ms[/dim]")

    result = diagnose(complaint or "checkup", settings=settings, lang=lang,
                      on_step=on_step)
    console.print(result.reply, markup=False)


@click.command()
@click.argument("goal")
@click.option("--url", "-u", default="http://127.0.0.1:7860/",
              show_default=True, help="起始 URL")
@click.option("--max-steps", default=15, show_default=True,
              type=click.IntRange(2, 30), help="步数上限")
@click.option("--headed", is_flag=True, help="有头浏览器(调试观察)")
@click.option("--allow-external", is_flag=True,
              help="允许跳出起始同源(默认禁止)")
def webtask(
    goal: str,
    url: str,
    max_steps: int,
    headed: bool,
    allow_external: bool,
) -> None:
    """网页操作 Agent — 目标 + URL,真实浏览器里快照/点击/填表直到完成。

    未达成以 FAILED 结束并退出码 1;需 API key 与 playwright。"""
    from dotenv import load_dotenv

    from .. import settings_store
    from ..config import load_settings
    from ..web_task import run_task

    load_dotenv()
    settings_store.apply_to_env()
    try:
        settings = load_settings()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(2)

    def on_step(step):
        mark = "⚠️ " if step.error else ""
        console.print(f"[dim]🖱️ {mark}{step.tool} {step.input} "
                      f"· {step.elapsed_ms} ms[/dim]")

    try:
        result = run_task(goal, url, settings, max_steps=max_steps,
                          headed=headed, allow_external=allow_external,
                          on_step=on_step)
    except Exception as exc:  # noqa: BLE001 — playwright missing etc.
        console.print(f"[red]{type(exc).__name__}: {exc}[/red]")
        sys.exit(2)
    console.print(result.reply, markup=False)
    if not result.success:
        sys.exit(1)


def register(cli) -> None:
    cli.add_command(mcp_toolbox_cmd)
    cli.add_command(mcp_stats)
    cli.add_command(uitest)
    cli.add_command(settings)
    cli.add_command(llmcost)
    cli.add_command(promptlab)
    cli.add_command(llmeval)
    cli.add_command(orchestrate)
    cli.add_command(relnotes)
    cli.add_command(bot)
    cli.add_command(docqa)
    cli.add_command(codefix)
    cli.add_command(triage_cmd)
    cli.add_command(doctor)
    cli.add_command(webtask)
