# -*- coding: utf-8 -*-
"""Gradio page for the data lineage agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Lineage", "/lineage")``.  Deterministic mode queries the graph
locally; the agent mode answers natural-language lineage questions with
streamed progress.
"""

from __future__ import annotations

import html
import threading
import time

import gradio as gr

from .config import load_settings
from .data_lineage import (
    LineageAgent,
    LineageGraph,
    LineageLogger,
    build_graph,
    load_lineage_config,
    mermaid_html,
    render_health,
    render_mermaid,
    render_path,
    render_path_mermaid,
    render_report,
    render_sla_impact,
    static_lineage,
)
from .data_lineage.snapshot import (
    diff_graphs,
    list_snapshots,
    load_snapshot,
    render_diff_markdown,
    save_snapshot,
)
from .ui import EventCollector

_logger = LineageLogger()

_I18N = {
    "en": {
        "title": "## 🩸 Data Lineage\n"
                 "Build a global lineage graph across SQL files / the Hive "
                 "metadata lineage table — upstream & downstream chains, "
                 "column-level impact analysis, SLA & baselines.",
        "ds_heading": "### Data Sources",
        "sql_dir_label": "SQL directory",
        "sql_dir_ph": "Directory containing *.sql files (scanned recursively)",
        "st_dir_label": "SeaTunnel config directory",
        "st_dir_ph": "Directory with SeaTunnel configs (*.conf/*.config/*.json), source→sink lineage",
        "use_hive": "Load from the Hive metadata lineage table (requires HIVE_HOST in .env)",
        "hive_adv": "Hive advanced options",
        "meta_table_label": "Lineage metadata table",
        "meta_table_ph": "Default zz.dwm_meta_table_lineage_df",
        "partition_label": "pt partition",
        "partition_ph": "Latest partition by default",
        "load_btn": "Build lineage graph",
        "not_loaded": "*No lineage data loaded yet*",
        "query_heading": "### Query",
        "table_label": "Target table",
        "table_info": "Pick from loaded tables or type freely, e.g. zz.dwm_orders_df",
        "direction_label": "Direction",
        "dir_both": "Full chain (upstream + downstream)",
        "dir_up": "Upstream only",
        "dir_down": "Downstream only",
        "depth_label": "Depth",
        "column_label": "Column (optional)",
        "column_ph": "Column-level impact analysis when set",
        "query_btn": "Query lineage",
        "search_label": "Table search",
        "search_ph": "Fuzzy search over loaded tables",
        "search_btn": "Search",
        "adv_heading": "### Advanced Analysis",
        "path_dst_label": "Path destination table",
        "path_dst_info": "Shortest lineage path from the target table to this table",
        "path_btn": "Find path",
        "sla_delay_label": "Assumed delay (hours)",
        "sla_btn": "SLA impact analysis",
        "health_btn": "Governance health check",
        "no_graph": "No lineage graph yet",
        "report_ph": "*The lineage report will appear here*",
        "mermaid_acc": "Mermaid source (copyable)",
        "agent_acc": "🤖 Agent Q&A (natural language, API key required)",
        "ask_label": "Question",
        "ask_ph": "e.g. Which downstream tables are affected if zz.dwd_orders_df.amount changes?",
        "ask_btn": "Ask",
        "need_source": "Provide a SQL directory or enable the Hive metadata option.",
        "built_stats": "✅ Lineage graph built: **{tables}** tables · **{edges}** edges · "
                       "**{col_edges}** column edges · {sla} SLA tables",
        "need_graph": "Build the lineage graph first.",
        "need_table": "Enter a target table.",
        "need_path_dst": "Enter the path destination table.",
        "not_found": "Table `{table}` not found in the lineage graph.",
        "similar": "Similar tables:",
        "need_keyword": "Enter a search keyword.",
        "no_match": "No tables match `{kw}`.",
        "need_question": "Enter a question.",
        "agent_running": "⏳ Analyzing…",
        "fail": "❌ **Analysis failed**: {exc}",
        "snap_heading": "### Snapshots",
        "snap_name_label": "Snapshot name (optional)",
        "save_snap_btn": "Save snapshot",
        "snap_dd_label": "Compare against snapshot",
        "diff_snap_btn": "Compare snapshots",
        "snap_saved": "✅ Snapshot saved: `{file}`",
        "need_snap": "Pick a snapshot to compare against.",
        "snap_not_found": "Snapshot `{snap}` not found.",
    },
    "zh": {
        "title": "## 🩸 数据表全链路血缘\n"
                 "跨 SQL 文件 / Hive 元数据血缘表构建全局血缘图 — "
                 "上下游链路、字段级影响分析、SLA 与基线展示。",
        "ds_heading": "### 数据源",
        "sql_dir_label": "SQL 目录",
        "sql_dir_ph": "包含 *.sql 文件的目录（递归扫描）",
        "st_dir_label": "SeaTunnel 配置目录",
        "st_dir_ph": "包含 SeaTunnel 配置（*.conf/*.config/*.json）的目录，提取 source→sink 血缘",
        "use_hive": "从 Hive 元数据血缘表加载（需 .env 配置 HIVE_HOST）",
        "hive_adv": "Hive 高级选项",
        "meta_table_label": "血缘元数据表",
        "meta_table_ph": "默认 zz.dwm_meta_table_lineage_df",
        "partition_label": "pt 分区",
        "partition_ph": "默认自动取最新分区",
        "load_btn": "构建血缘图",
        "not_loaded": "*尚未加载血缘数据*",
        "query_heading": "### 查询",
        "table_label": "目标表",
        "table_info": "从已加载表中选择或直接输入，如 zz.dwm_orders_df",
        "direction_label": "方向",
        "dir_both": "全链路（上游 + 下游）",
        "dir_up": "仅上游",
        "dir_down": "仅下游",
        "depth_label": "深度",
        "column_label": "字段（可选）",
        "column_ph": "填写后做字段级影响分析",
        "query_btn": "查询血缘",
        "search_label": "表名搜索",
        "search_ph": "关键字模糊搜索已加载的表",
        "search_btn": "搜索",
        "adv_heading": "### 高级分析",
        "path_dst_label": "路径终点表",
        "path_dst_info": "查询目标表到该表的最短血缘路径",
        "path_btn": "查询路径",
        "sla_delay_label": "假设延迟（小时）",
        "sla_btn": "SLA 影响分析",
        "health_btn": "治理体检",
        "no_graph": "暂无血缘图",
        "report_ph": "*血缘报告将显示在这里*",
        "mermaid_acc": "Mermaid 源码（可复制）",
        "agent_acc": "🤖 Agent 问答（自然语言，需 API key）",
        "ask_label": "问题",
        "ask_ph": "例：改 zz.dwd_orders_df 的 amount 字段会影响哪些下游表？",
        "ask_btn": "提问",
        "need_source": "请至少提供 SQL 目录或勾选 Hive 元数据。",
        "built_stats": "✅ 血缘图已构建：**{tables}** 表 · **{edges}** 边 · "
                       "**{col_edges}** 字段边 · SLA 表 {sla} 张",
        "need_graph": "请先构建血缘图。",
        "need_table": "请输入目标表。",
        "need_path_dst": "请输入路径终点表。",
        "not_found": "未在血缘图中找到表 `{table}`。",
        "similar": "相近的表：",
        "need_keyword": "请输入搜索关键字。",
        "no_match": "没有匹配 `{kw}` 的表。",
        "need_question": "请输入问题。",
        "agent_running": "⏳ 分析中…",
        "fail": "❌ **分析失败**：{exc}",
        "snap_heading": "### 快照",
        "snap_name_label": "快照名（可选）",
        "save_snap_btn": "保存快照",
        "snap_dd_label": "对比快照",
        "diff_snap_btn": "快照对比",
        "snap_saved": "✅ 快照已保存：`{file}`",
        "need_snap": "请选择要对比的快照。",
        "snap_not_found": "找不到快照 `{snap}`。",
    },
}

_PHASE_LABELS = {
    "en": {"thinking": "Thinking…", "executing_tools": "Executing tools…"},
    "zh": {"thinking": "思考中…", "executing_tools": "执行工具中…"},
}


def _log_ui(start: float, graph: LineageGraph, *, query: str, mode: str,
            direction: str = "", chain_stats: dict | None = None) -> None:
    _logger.log(
        query=query, direction=direction, mode=mode, source="ui",
        graph_stats=graph.stats(), chain_stats=chain_stats,
        elapsed_ms=int((time.time() - start) * 1000),
    )


def _lt(lang: str, key: str) -> str:
    return _I18N.get(lang, _I18N["en"]).get(key, _I18N["en"].get(key, key))


def _direction_choices(lang: str) -> list[tuple[str, str]]:
    return [(_lt(lang, "dir_both"), "both"),
            (_lt(lang, "dir_up"), "upstream"),
            (_lt(lang, "dir_down"), "downstream")]


def _err_md(exc: Exception, lang: str = "zh") -> str:
    return _lt(lang, "fail").format(exc=exc)


def _no_graph_html(lang: str) -> str:
    return f"<p style='color:#9ca3af;'>{_lt(lang, 'no_graph')}</p>"


def _mermaid_iframe(mermaid_src: str, lang: str = "zh") -> str:
    if not mermaid_src.strip():
        return _no_graph_html(lang)
    doc = mermaid_html(mermaid_src)
    return (
        f'<iframe srcdoc="{html.escape(doc)}" '
        'style="width:100%;height:480px;border:1px solid #e5e7eb;'
        'border-radius:8px;background:#fff;"></iframe>'
    )


def _table_choices(graph: LineageGraph | None) -> list[str]:
    return sorted(graph.nodes) if graph is not None else []


def _snapshot_choices() -> list[tuple[str, str]]:
    return [
        (f"{s['name'] or s['file']}（{s['saved_at']}）", s["file"])
        for s in list_snapshots()
    ]


def _not_found_md(graph: LineageGraph, table: str, lang: str) -> str:
    msg = _lt(lang, "not_found").format(table=table)
    suggestions = graph.suggest(table, 10)
    if suggestions:
        msg += f"\n\n{_lt(lang, 'similar')}\n" + "\n".join(
            f"- `{name}`" for name in suggestions
        )
    return msg


def _fmt_agent_events(events: list[dict], lang: str) -> str:
    """Render the agent's streamed events as a markdown progress log."""
    phases = _PHASE_LABELS.get(lang, _PHASE_LABELS["en"])
    lines: list[str] = []
    delta: list[str] = []
    for ev in events:
        t = ev.get("type")
        if t == "text_delta":
            delta.append(ev.get("text", ""))
            continue
        if t == "text":
            delta.clear()
            continue
        if t == "step":
            label = phases.get(ev.get("phase", ""), ev.get("phase", ""))
            lines.append(f"⏳ **Step {ev.get('iteration', '?')}/{ev.get('max', '?')}** — {label}")
        elif t == "tool_call":
            name = ev.get("name", "?")
            args = ", ".join(
                f"{k}={repr(v)[:60]}" for k, v in (ev.get("input") or {}).items()
            )
            lines.append(f"🔧 `{name}`（{args}）" if args else f"🔧 `{name}`")
    if delta:
        text = "".join(delta).strip()
        if text:
            lines.append(text + " ▌")
    return "\n\n".join(lines) if lines else _lt(lang, "agent_running")


def render_lineage_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _lt(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)
    graph_state = gr.State(None)  # LineageGraph | None

    # The global CSS locks .gradio-container to 100vh with overflow hidden,
    # so the page needs its own scroll container.
    with gr.Column(elem_classes=["st-lin-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            lang_dd = gr.Dropdown(
                choices=["English", "中文"], value="English",
                show_label=False, container=False, min_width=140, scale=0,
            )

        with gr.Row():
            # ── data source panel ──
            with gr.Column(scale=2, elem_classes=["st-lin-side"]):
                ds_heading_md = gr.Markdown(t("ds_heading"))
                sql_dir_box = gr.Textbox(
                    label=t("sql_dir_label"), placeholder=t("sql_dir_ph"),
                )
                st_dir_box = gr.Textbox(
                    label=t("st_dir_label"), placeholder=t("st_dir_ph"),
                )
                use_hive_cb = gr.Checkbox(label=t("use_hive"), value=False)
                with gr.Accordion(t("hive_adv"), open=False) as hive_acc:
                    meta_table_box = gr.Textbox(
                        label=t("meta_table_label"), placeholder=t("meta_table_ph"),
                    )
                    partition_box = gr.Textbox(
                        label=t("partition_label"), placeholder=t("partition_ph"),
                    )
                load_btn = gr.Button(t("load_btn"), variant="primary")
                graph_stats_md = gr.Markdown(t("not_loaded"))

                query_heading_md = gr.Markdown(t("query_heading"))
                table_box = gr.Dropdown(
                    choices=[], value=None, allow_custom_value=True,
                    label=t("table_label"), info=t("table_info"),
                )
                with gr.Row():
                    direction_dd = gr.Dropdown(
                        choices=_direction_choices(lang0), value="both",
                        label=t("direction_label"),
                    )
                    depth_sl = gr.Slider(1, 10, value=3, step=1, label=t("depth_label"))
                column_box = gr.Textbox(
                    label=t("column_label"), placeholder=t("column_ph"),
                )
                query_btn = gr.Button(t("query_btn"), variant="primary")
                search_box = gr.Textbox(label=t("search_label"), placeholder=t("search_ph"))
                search_btn = gr.Button(t("search_btn"), size="sm")
                search_md = gr.Markdown("")

                adv_heading_md = gr.Markdown(t("adv_heading"))
                path_dst_dd = gr.Dropdown(
                    choices=[], value=None, allow_custom_value=True,
                    label=t("path_dst_label"), info=t("path_dst_info"),
                )
                path_btn = gr.Button(t("path_btn"), size="sm")
                with gr.Row():
                    sla_delay_num = gr.Number(
                        value=1, minimum=0, label=t("sla_delay_label"),
                    )
                    sla_btn = gr.Button(t("sla_btn"), size="sm")
                health_btn = gr.Button(t("health_btn"), size="sm")

                snap_heading_md = gr.Markdown(t("snap_heading"))
                snap_name_box = gr.Textbox(label=t("snap_name_label"))
                save_snap_btn = gr.Button(t("save_snap_btn"), size="sm")
                snap_dd = gr.Dropdown(
                    choices=[], value=None,
                    label=t("snap_dd_label"),
                )
                diff_snap_btn = gr.Button(t("diff_snap_btn"), size="sm")
                snap_md = gr.Markdown("")

            # ── result panel ──
            with gr.Column(scale=4, elem_classes=["st-lin-main"]):
                mermaid_frame = gr.HTML(_no_graph_html(lang0))
                report_md = gr.Markdown(t("report_ph"))
                with gr.Accordion(t("mermaid_acc"), open=False) as mermaid_acc:
                    mermaid_src_box = gr.Code(label="mermaid", language="markdown")

        # Hidden bridge for mermaid node clicks (filled by iframe JS, see
        # data_lineage/render.py mermaid_html template).
        node_jump_box = gr.Textbox(
            elem_id="st-lin-node-jump", elem_classes=["st-lin-hidden"],
            container=False, show_label=False,
        )
        node_jump_btn = gr.Button(
            "", elem_id="st-lin-node-jump-btn", elem_classes=["st-lin-hidden"],
        )

        # ── agent chat ──
        with gr.Accordion(t("agent_acc"), open=False) as agent_acc:
            ask_box = gr.Textbox(label=t("ask_label"), lines=2, placeholder=t("ask_ph"))
            ask_btn = gr.Button(t("ask_btn"), variant="primary")
            answer_md = gr.Markdown("")

    # ── callbacks ──

    def do_load(sql_dir: str, st_dir: str, use_hive: bool, meta_table: str,
                partition: str, lang: str):
        sql_dir = (sql_dir or "").strip()
        st_dir = (st_dir or "").strip()
        meta_table = (meta_table or "").strip() or None
        partition = (partition or "").strip() or None
        if not sql_dir and not st_dir and not use_hive:
            return None, _lt(lang, "need_source"), gr.update(), gr.update()
        try:
            graph, warnings = build_graph(
                sql_dir=sql_dir or None, use_hive=use_hive,
                meta_table=meta_table, partition=partition,
                seatunnel_dir=st_dir or None,
            )
        except Exception as exc:  # noqa: BLE001 — surface any failure in the UI
            return None, _err_md(exc, lang), gr.update(), gr.update()
        stats = graph.stats()
        lines = [_lt(lang, "built_stats").format(
            tables=stats["tables"], edges=stats["edges"],
            col_edges=stats["column_edges"], sla=stats["sla_tables"],
        )]
        lines.extend(f"- ⚠️ {w}" for w in warnings)
        choices = _table_choices(graph)
        return (
            graph, "\n".join(lines),
            gr.update(choices=choices), gr.update(choices=choices),
        )

    def _query_core(graph: LineageGraph, table: str, direction: str,
                    depth: int, column: str | None, lang: str):
        """Shared deterministic query → (mermaid_html, report_md, mermaid_src)."""
        start = time.time()
        config = load_lineage_config()
        report = static_lineage(
            graph, table, direction, depth, column=column, config=config,
        )
        chain = report.chain
        if chain and chain.missing_root:
            return _no_graph_html(lang), _not_found_md(graph, table, lang), ""
        _log_ui(
            start, graph, query=table, direction=direction, mode="static",
            chain_stats={
                "upstream": chain.upstream_count if chain else 0,
                "downstream": chain.downstream_count if chain else 0,
            },
        )
        return (
            _mermaid_iframe(report.mermaid, lang),
            render_report(report),
            report.mermaid,
        )

    def do_query(graph: LineageGraph | None, table: str, direction: str,
                 depth: float, column: str, lang: str):
        table = (table or "").strip()
        if graph is None:
            return _no_graph_html(lang), _lt(lang, "need_graph"), ""
        if not table:
            return _no_graph_html(lang), _lt(lang, "need_table"), ""
        try:
            return _query_core(
                graph, table, direction, int(depth),
                (column or "").strip() or None, lang,
            )
        except Exception as exc:  # noqa: BLE001 — surface any failure in the UI
            return _no_graph_html(lang), _err_md(exc, lang), ""

    def do_node_jump(graph: LineageGraph | None, table: str, direction: str,
                     depth: float, lang: str):
        """Mermaid node click → select the table and re-run the query."""
        table = (table or "").strip()
        if graph is None or not table:
            return gr.update(), gr.update(), gr.update(), gr.update()
        try:
            frame, report, src = _query_core(
                graph, table, direction, int(depth), None, lang,
            )
        except Exception as exc:  # noqa: BLE001
            return gr.update(value=table), gr.update(), _err_md(exc, lang), gr.update()
        return gr.update(value=table), frame, report, src

    def do_path(graph: LineageGraph | None, src: str, dst: str, lang: str):
        src = (src or "").strip()
        dst = (dst or "").strip()
        if graph is None:
            return gr.update(), _lt(lang, "need_graph"), gr.update()
        if not src:
            return gr.update(), _lt(lang, "need_table"), gr.update()
        if not dst:
            return gr.update(), _lt(lang, "need_path_dst"), gr.update()
        for name in (src, dst):
            if graph.get(name) is None:
                return gr.update(), _not_found_md(graph, name, lang), gr.update()
        start = time.time()
        path = graph.path_between(src, dst)
        _log_ui(start, graph, query=f"{src}->{dst}", mode="path")
        mermaid = render_path_mermaid(path, graph) if path else ""
        return (
            _mermaid_iframe(mermaid, lang) if mermaid else gr.update(),
            render_path(path, src, dst, graph),
            mermaid or gr.update(),
        )

    def do_sla(graph: LineageGraph | None, table: str, delay: float,
               depth: float, lang: str):
        table = (table or "").strip()
        if graph is None:
            return gr.update(), _lt(lang, "need_graph"), gr.update()
        if not table:
            return gr.update(), _lt(lang, "need_table"), gr.update()
        start = time.time()
        config = load_lineage_config()
        # 报表和图使用同一深度（同一次 BFS 结果），否则报表列出的表可能不在图中
        chain = graph.downstream_of(table, int(depth), config.max_nodes)
        impact = graph.sla_impact(
            table, float(delay or 0), depth=int(depth),
            max_nodes=config.max_nodes, chain=chain,
        )
        if impact.missing_root:
            return gr.update(), _not_found_md(graph, table, lang), gr.update()
        mermaid = render_mermaid(chain, config.max_mermaid_nodes)
        _log_ui(start, graph, query=table, mode="sla")
        return (
            _mermaid_iframe(mermaid, lang),
            render_sla_impact(impact),
            mermaid,
        )

    def do_health(graph: LineageGraph | None, lang: str):
        if graph is None:
            return _lt(lang, "need_graph")
        start = time.time()
        report = graph.health_check()
        _log_ui(start, graph, query="health_check", mode="health")
        return render_health(report)

    def do_save_snap(graph: LineageGraph | None, name: str, lang: str):
        if graph is None:
            return _lt(lang, "need_graph"), gr.update()
        try:
            path = save_snapshot(graph, name=(name or "").strip())
        except Exception as exc:  # noqa: BLE001 — surface any failure in the UI
            return _err_md(exc, lang), gr.update()
        return (
            _lt(lang, "snap_saved").format(file=path.name),
            gr.update(choices=_snapshot_choices(), value=path.name),
        )

    def do_diff_snap(graph: LineageGraph | None, snap: str, lang: str):
        if graph is None:
            return _lt(lang, "need_graph")
        snap = (snap or "").strip()
        if not snap:
            return _lt(lang, "need_snap")
        try:
            old = load_snapshot(snap)
            if old is None:
                return _lt(lang, "snap_not_found").format(snap=snap)
            return render_diff_markdown(diff_graphs(old, graph))
        except Exception as exc:  # noqa: BLE001 — surface any failure in the UI
            return _err_md(exc, lang)

    def do_search(graph: LineageGraph | None, keyword: str, lang: str):
        keyword = (keyword or "").strip()
        if graph is None:
            return _lt(lang, "need_graph")
        if not keyword:
            return _lt(lang, "need_keyword")
        matches = graph.search(keyword)
        if not matches:
            return _lt(lang, "no_match").format(kw=keyword)
        return "\n".join(
            f"- `{n.name}`" + (f"（{n.layer}）" if n.layer else "")
            for n in matches
        )

    def do_ask(graph: LineageGraph | None, question: str,
               sql_dir: str, st_dir: str, use_hive: bool, meta_table: str,
               partition: str, lang: str):
        question = (question or "").strip()
        if not question:
            yield _lt(lang, "need_question"), gr.update(), gr.update()
            return
        if graph is None:
            yield _lt(lang, "need_graph"), gr.update(), gr.update()
            return

        collector = EventCollector()
        done = threading.Event()
        result: dict = {}

        def worker() -> None:
            try:
                settings = load_settings()
                agent = LineageAgent(
                    settings, graph=graph,
                    sql_dir=(sql_dir or "").strip() or None,
                    seatunnel_dir=(st_dir or "").strip() or None,
                    hive_available=use_hive,
                    meta_table=(meta_table or "").strip() or None,
                    partition=(partition or "").strip() or None,
                    on_event=collector.on_event,
                )
                result["answer"] = agent.analyze(question)
                result["mermaid"] = agent.runtime.last_mermaid
            except Exception as exc:  # noqa: BLE001 — surfaced in the UI below
                result["error"] = exc
            finally:
                done.set()

        start = time.time()
        threading.Thread(target=worker, daemon=True).start()
        yield _lt(lang, "agent_running"), gr.update(), gr.update()
        while not done.wait(0.4):
            yield _fmt_agent_events(collector.snapshot(), lang), gr.update(), gr.update()

        if "error" in result:
            yield _err_md(result["error"], lang), gr.update(), gr.update()
            return
        _log_ui(start, graph, query=question, mode="agent")
        answer = result.get("answer", "")
        mermaid = result.get("mermaid", "")
        if mermaid:
            yield answer, _mermaid_iframe(mermaid, lang), mermaid
        else:
            yield answer, gr.update(), gr.update()

    def switch_lang(choice: str, direction_value: str):
        lang = "zh" if choice == "中文" else "en"
        s = lambda k: _lt(lang, k)  # noqa: E731
        return (
            lang,
            gr.update(value=s("title")),
            gr.update(value=s("ds_heading")),
            gr.update(label=s("sql_dir_label"), placeholder=s("sql_dir_ph")),
            gr.update(label=s("st_dir_label"), placeholder=s("st_dir_ph")),
            gr.update(label=s("use_hive")),
            gr.update(label=s("hive_adv")),
            gr.update(label=s("meta_table_label"), placeholder=s("meta_table_ph")),
            gr.update(label=s("partition_label"), placeholder=s("partition_ph")),
            gr.update(value=s("load_btn")),
            gr.update(value=s("query_heading")),
            gr.update(label=s("table_label"), info=s("table_info")),
            gr.update(choices=_direction_choices(lang), value=direction_value,
                      label=s("direction_label")),
            gr.update(label=s("depth_label")),
            gr.update(label=s("column_label"), placeholder=s("column_ph")),
            gr.update(value=s("query_btn")),
            gr.update(label=s("search_label"), placeholder=s("search_ph")),
            gr.update(value=s("search_btn")),
            gr.update(value=s("adv_heading")),
            gr.update(label=s("path_dst_label"), info=s("path_dst_info")),
            gr.update(value=s("path_btn")),
            gr.update(label=s("sla_delay_label")),
            gr.update(value=s("sla_btn")),
            gr.update(value=s("health_btn")),
            gr.update(value=s("snap_heading")),
            gr.update(label=s("snap_name_label")),
            gr.update(value=s("save_snap_btn")),
            gr.update(label=s("snap_dd_label")),
            gr.update(value=s("diff_snap_btn")),
            gr.update(label=s("mermaid_acc")),
            gr.update(label=s("agent_acc")),
            gr.update(label=s("ask_label"), placeholder=s("ask_ph")),
            gr.update(value=s("ask_btn")),
        )

    lang_dd.change(
        switch_lang,
        inputs=[lang_dd, direction_dd],
        outputs=[
            lang_state, title_md, ds_heading_md, sql_dir_box, st_dir_box,
            use_hive_cb,
            hive_acc, meta_table_box, partition_box, load_btn,
            query_heading_md, table_box, direction_dd, depth_sl, column_box,
            query_btn, search_box, search_btn, adv_heading_md, path_dst_dd,
            path_btn, sla_delay_num, sla_btn, health_btn,
            snap_heading_md, snap_name_box, save_snap_btn, snap_dd,
            diff_snap_btn, mermaid_acc,
            agent_acc, ask_box, ask_btn,
        ],
    )
    load_btn.click(
        do_load,
        inputs=[sql_dir_box, st_dir_box, use_hive_cb, meta_table_box,
                partition_box, lang_state],
        outputs=[graph_state, graph_stats_md, table_box, path_dst_dd],
    )
    query_btn.click(
        do_query,
        inputs=[graph_state, table_box, direction_dd, depth_sl, column_box,
                lang_state],
        outputs=[mermaid_frame, report_md, mermaid_src_box],
    )
    node_jump_btn.click(
        do_node_jump,
        inputs=[graph_state, node_jump_box, direction_dd, depth_sl, lang_state],
        outputs=[table_box, mermaid_frame, report_md, mermaid_src_box],
    )
    path_btn.click(
        do_path,
        inputs=[graph_state, table_box, path_dst_dd, lang_state],
        outputs=[mermaid_frame, report_md, mermaid_src_box],
    )
    sla_btn.click(
        do_sla,
        inputs=[graph_state, table_box, sla_delay_num, depth_sl, lang_state],
        outputs=[mermaid_frame, report_md, mermaid_src_box],
    )
    health_btn.click(
        do_health, inputs=[graph_state, lang_state], outputs=[report_md],
    )
    search_btn.click(
        do_search, inputs=[graph_state, search_box, lang_state],
        outputs=[search_md],
    )
    save_snap_btn.click(
        do_save_snap, inputs=[graph_state, snap_name_box, lang_state],
        outputs=[snap_md, snap_dd],
    )
    diff_snap_btn.click(
        do_diff_snap, inputs=[graph_state, snap_dd, lang_state],
        outputs=[report_md],
    )
    ask_btn.click(
        do_ask,
        inputs=[graph_state, ask_box, sql_dir_box, st_dir_box, use_hive_cb,
                meta_table_box, partition_box, lang_state],
        outputs=[answer_md, mermaid_frame, mermaid_src_box],
    )
    # Snapshot listing reads every snapshot JSON — defer it off server startup
    # to page load so building the app stays cheap.
    app.load(
        lambda: gr.update(choices=_snapshot_choices()), outputs=[snap_dd],
    )
