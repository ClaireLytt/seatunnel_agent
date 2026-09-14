"""Gradio page for the Text2SQL (Chat BI) agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Text2SQL", "/text2sql")``. Keeps its own holders/state so it is
fully independent from the SeaTunnel page.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import gradio as gr

from .config import Settings, load_settings
from .text2sql.executor import (
    HiveConfig,
    hive_config_from_env,
    schema_ddl_path_from_env,
)
from .text2sql.qlog import QueryLogger
from .text2sql.schema import SchemaStore


_TOOL_EMOJI = {
    "match_tables": "\U0001f50d",
    "get_table_schema": "\U0001f4d6",
    "get_max_partition": "\U0001f4c5",
    "execute_sql": "⚡",
    "export_csv": "\U0001f4be",
}

_TOOL_LABEL_I18N: dict[str, dict[str, str]] = {
    "en": {
        "match_tables": "Match Tables",
        "get_table_schema": "Get Table Schema",
        "get_max_partition": "Get Max Partition",
        "execute_sql": "Execute SQL",
        "export_csv": "Export CSV",
    },
    "zh": {
        "match_tables": "匹配候选表",
        "get_table_schema": "读取表结构",
        "get_max_partition": "获取最大分区",
        "execute_sql": "执行 SQL",
        "export_csv": "导出 CSV",
    },
}

_T2S_I18N: dict[str, dict[str, str]] = {
    "en": {
        "sidebar_title": "### \U0001f5c4 Data Source Config",
        "schema_label": "Schema DDL Path (optional whitelist)",
        "loaded_from_hive": "Loaded {n} tables from Hive ({db})",
        "hive_host": "Hive Host",
        "port": "Port",
        "database": "Database",
        "connect": "Connect",
        "status_label": "Status",
        "status_default": "Not connected",
        "new_chat": "+ New Chat",
        "export_csv": "Export CSV",
        "history": "\U0001f4dc Query History",
        "refresh": "Refresh",
        "input_placeholder": "Describe the data you want to query, e.g.: show total sales by city...",
        "connect_first": "Please click **Connect** on the left sidebar to load Schema and Hive config first.",
        "no_export": "No query result to export. Please run a query first.",
        "placeholder_title": "Smart Data Query · Query Hive data with natural language",
        "candidates": "Candidate Tables",
        "score": "score",
        "type": "type",
        "matched_cols": "matched columns",
        "table_type": "Type",
        "cols_count": "columns",
        "partitioned": "partitioned",
        "max_partition": "Max Partition",
        "exec_success": "SQL Executed",
        "elapsed": "elapsed",
        "rows": "rows",
        "truncated": "(truncated)",
        "csv_exported": "CSV Exported",
        "no_result": "(No results)",
        "reload_schema": "Reload Schema",
        "schema_reloaded": "Schema reloaded: {n} tables",
        "thinking": "Thinking",
        "generating": "Generating...",
        "executing": "Executing...",
        "done": "Done, elapsed",
        "stopped": "Stopped by user.",
        "loaded_tables": "Loaded {n} tables",
        "hive_not_configured": "Hive not configured (SQL generation only)",
        "model": "Model",
        "schema_not_found": "Schema file not found",
        "schema_parse_fail": "Schema parse failed",
        "no_tables": "No tables parsed from",
        "llm_load_fail": "LLM config load failed",
        "port_not_number": "Port must be a number",
        "failed": "failed",
        "select_tables": "Tables ({n})",
        "filtered_tables": "Filtered to {n} tables",
        "select_all": "All",
        "deselect_all": "None",
        "confirm": "Confirm",
        "cancel": "Cancel",
        "search_placeholder": "🔍 Search tables...",
    },
    "zh": {
        "sidebar_title": "### \U0001f5c4 数据源配置",
        "schema_label": "Schema DDL 路径（可选白名单）",
        "loaded_from_hive": "从 Hive ({db}) 加载了 {n} 张表",
        "hive_host": "Hive Host",
        "port": "Port",
        "database": "Database",
        "connect": "连接 / Connect",
        "status_label": "状态",
        "status_default": "未连接",
        "new_chat": "+ 新建对话",
        "export_csv": "导出结果 CSV",
        "history": "\U0001f4dc 历史查询",
        "refresh": "刷新",
        "input_placeholder": "用自然语言描述你要查的数据，例如：查最近30天的入库单量...",
        "connect_first": "请先点击左侧 **连接 / Connect** 加载 Schema 和 Hive 配置。",
        "no_export": "没有可导出的查询结果，请先执行一次查询。",
        "placeholder_title": "智能问数 · 用自然语言查 Hive 数据",
        "candidates": "候选表",
        "score": "得分",
        "type": "类型",
        "matched_cols": "命中字段",
        "table_type": "类型",
        "cols_count": "字段数",
        "partitioned": "分区表",
        "max_partition": "最大分区",
        "exec_success": "SQL 执行成功",
        "elapsed": "耗时",
        "rows": "行",
        "truncated": "（已截断）",
        "csv_exported": "CSV 已导出",
        "no_result": "(无结果)",
        "reload_schema": "重新加载 Schema",
        "schema_reloaded": "Schema 已重新加载: {n} 张表",
        "thinking": "Thinking",
        "generating": "生成中...",
        "executing": "执行中...",
        "done": "完成，耗时",
        "stopped": "已被用户中断。",
        "loaded_tables": "已加载 {n} 张表",
        "hive_not_configured": "Hive 未配置（仅可生成 SQL）",
        "model": "模型",
        "schema_not_found": "Schema 文件不存在",
        "schema_parse_fail": "Schema 解析失败",
        "no_tables": "未从以下文件解析到任何表",
        "llm_load_fail": "LLM 配置加载失败",
        "port_not_number": "端口号必须是数字",
        "failed": "失败",
        "select_tables": "查询表 ({n})",
        "filtered_tables": "已筛选 {n} 张表",
        "select_all": "全选",
        "deselect_all": "清空",
        "confirm": "确认",
        "cancel": "取消",
        "search_placeholder": "🔍 搜索表...",
    },
}


def _t2s(lang: str, key: str) -> str:
    return _T2S_I18N.get(lang, _T2S_I18N["en"]).get(key, _T2S_I18N["en"].get(key, key))


def _md_table(columns: list[str], rows: list[list[Any]], max_rows: int = 20, lang: str = "en") -> str:
    if not columns:
        return _t2s(lang, "no_result")
    header = "| " + " | ".join(str(c) for c in columns) + " |"
    sep = "|" + "|".join(["---"] * len(columns)) + "|"
    lines = [header, sep]
    for r in rows[:max_rows]:
        cells = [str(v) if v is not None else "" for v in r]
        lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    return "\n".join(lines)


def _format_tool_result(name: str, raw: str, lang: str = "en") -> str:
    t = lambda k: _t2s(lang, k)
    labels = _TOOL_LABEL_I18N.get(lang, _TOOL_LABEL_I18N["en"])
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return f"\U0001f4e6 **{name}**\n```\n{str(raw)[:500]}\n```"

    label = labels.get(name, name)

    if data.get("error"):
        return f"❌ **{label} {t('failed')}**\n\n{str(data['error'])[:500]}"

    if name == "match_tables":
        lines = [f"\U0001f50d **{t('candidates')}** ({data.get('count', 0)}):", ""]
        for c in data.get("candidates", []):
            cols = ", ".join(c.get("matched_columns", [])[:5])
            lines.append(
                f"- **`{c['table']}`** — {c.get('comment', '')} "
                f"({t('score')} {c.get('score', 0)}, {t('type')} {c.get('table_type', '?')})"
                + (f", {t('matched_cols')}: {cols}" if cols else "")
            )
        return "\n".join(lines)

    if name == "get_table_schema":
        cols = data.get("columns", [])
        parts = [
            f"\U0001f4d6 **`{data.get('table', '?')}`** — {data.get('comment', '')}",
            f"{t('table_type')}: {data.get('table_type', '?')} · {t('cols_count')}: {len(cols)}"
            + (f" · {t('partitioned')}" if data.get("partitioned") else ""),
        ]
        if data.get("partition_columns"):
            pc = ", ".join(
                f"`{p['name']}`({p.get('comment', '')})"
                for p in data["partition_columns"]
            )
            parts.append(f"Partition: {pc}")
        return "\n\n".join(parts)

    if name == "get_max_partition":
        return (
            f"\U0001f4c5 **{t('max_partition')}** `{data.get('table', '?')}` → "
            f"`{data.get('partition_column', 'pt')}={data.get('max_partition', '?')}`"
        )

    if name == "execute_sql":
        sql = data.get("sql", "")
        lines = [
            f"⚡ **{t('exec_success')}**",
            "",
            f"```sql\n{sql}\n```",
            f"⏱ {t('elapsed')} **{data.get('elapsed_ms', '?')} ms** · "
            f"**{data.get('row_count', 0)}** {t('rows')}"
            + (f" {t('truncated')}" if data.get("truncated") else ""),
            "",
            _md_table(data.get("columns", []), data.get("preview_rows", []), lang=lang),
        ]
        return "\n".join(lines)

    if name == "export_csv":
        return (
            f"\U0001f4be **{t('csv_exported')}** ({data.get('row_count', 0)} {t('rows')})\n\n"
            f"`{data.get('csv_path', '?')}`"
        )

    return f"\U0001f4e6 **{label}**\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:600]}\n```"


def _format_events(events: list[dict[str, Any]], start_time: float | None = None, lang: str = "en") -> list[dict[str, str]]:
    t = lambda k: _t2s(lang, k)
    labels = _TOOL_LABEL_I18N.get(lang, _TOOL_LABEL_I18N["en"])
    messages: list[dict[str, str]] = []
    delta_buffer: list[str] = []

    def _flush() -> None:
        if delta_buffer:
            acc = "".join(delta_buffer)
            if acc.strip():
                messages.append({"role": "assistant", "content": acc + " ▌"})
            delta_buffer.clear()

    for ev in events:
        tp = ev["type"]
        if tp == "text_delta":
            delta_buffer.append(ev.get("text", ""))
            continue
        if tp == "text":
            delta_buffer.clear()
        elif delta_buffer:
            _flush()

        if tp == "step":
            phase = ev.get("phase", "")
            phase_label = {"thinking": t("generating"), "executing_tools": t("executing")}.get(phase, phase)
            elapsed = f" ({time.time() - start_time:.1f}s)" if start_time else ""
            messages.append({
                "role": "assistant",
                "content": f"⏳ **Step {ev.get('iteration', '?')}** — {phase_label}{elapsed}",
            })
        elif tp == "thinking":
            text = ev.get("text", "")
            if text:
                preview = text[:600] + ("..." if len(text) > 600 else "")
                messages.append({"role": "assistant", "content": f"\U0001f4ad **{t('thinking')}**\n\n{preview}"})
        elif tp == "text":
            if ev.get("text"):
                messages.append({"role": "assistant", "content": ev["text"]})
        elif tp == "tool_call":
            name = ev.get("name", "?")
            emoji = _TOOL_EMOJI.get(name, "\U0001f527")
            label = labels.get(name, name)
            inp = ev.get("input", {})
            if name == "execute_sql" and inp.get("sql"):
                body = f"```sql\n{inp['sql']}\n```"
            else:
                args = ", ".join(f"{k}={repr(v)[:100]}" for k, v in inp.items())
                body = f"`{args}`" if args else ""
            messages.append({"role": "assistant", "content": f"{emoji} **{label}**\n{body}"})
        elif tp == "tool_result":
            messages.append({
                "role": "assistant",
                "content": _format_tool_result(ev.get("name", "?"), ev.get("result", "{}"), lang),
            })
        elif tp == "usage":
            inp_t, out_t = ev.get("input_tokens", 0), ev.get("output_tokens", 0)
            if inp_t or out_t:
                messages.append({"role": "assistant", "content": f"📊 Tokens: {inp_t:,} in / {out_t:,} out"})

    _flush()
    return messages


def _history_rows(logger: QueryLogger, n: int = 100) -> list[list[str]]:
    rows = []
    for i, rec in enumerate(reversed(logger.recent(n))):
        status = rec.get("status", "")
        badge = "✅" if status == "success" else "❌" if status == "error" else "⏳"
        elapsed = rec.get("exec_time_ms")
        elapsed_str = f"{elapsed}ms" if elapsed is not None else ""
        ts = rec.get("timestamp", "")
        if "T" in ts:
            ts = ts.replace("T", " ")
        sql = rec.get("generated_sql") or ""
        if len(sql) > 120:
            sql = sql[:120] + "..."
        rows.append([
            str(i),
            ts,
            rec.get("user_query", ""),
            f"{badge}",
            elapsed_str,
            sql,
        ])
    return rows


def render_history_page() -> None:
    """Full-page query history viewer."""
    logger = QueryLogger()

    with gr.Column(elem_classes=["st-history-page"]):
        lang_state = gr.State("en")
        with gr.Row(elem_classes=["st-topbar-row"]):
            gr.HTML('<div class="st-topbar-spacer"></div>')
            lang_dd = gr.Dropdown(
                choices=["English", "中文"],
                value="English",
                show_label=False,
                container=False,
                min_width=140,
                elem_classes=["st-lang-dd"],
            )

        title_md = gr.Markdown("## Query History")

        with gr.Row(elem_classes=["st-hist-toolbar"]):
            back_btn = gr.Button("← Back", variant="secondary", size="sm",
                                 elem_classes=["st-hist-btn"])
            refresh_btn = gr.Button("↻ Refresh", variant="secondary", size="sm",
                                    elem_classes=["st-hist-btn"])
            delete_btn = gr.Button("✕ Delete Selected", variant="stop", size="sm",
                                   elem_classes=["st-hist-btn"])
            clear_btn = gr.Button("Clear All", variant="stop", size="sm",
                                  elem_classes=["st-hist-btn"])

        selected_state = gr.State([])
        selected_info = gr.Markdown("", elem_classes=["st-hist-sel-info"])

        history_table = gr.Dataframe(
            headers=["#", "Time", "Question", "", "Elapsed", "SQL"],
            value=_history_rows(logger),
            interactive=False,
            wrap=True,
            column_widths=["36px", "140px", "32%", "32px", "60px", "38%"],
        )

    def _on_select(evt: gr.SelectData, current: list):
        current = list(current)
        row = evt.index[0]
        if row in current:
            current.remove(row)
        else:
            current.append(row)
        current.sort()
        if current:
            info = f"**{len(current)}** selected: #{', #'.join(str(r) for r in current)}"
        else:
            info = ""
        return current, info

    def _refresh():
        return _history_rows(logger), [], ""

    def _delete_selected(selected: list):
        if selected:
            logger.delete(selected)
        return _history_rows(logger), [], ""

    def _clear():
        logger.clear()
        return [], [], ""

    def _switch_lang(choice):
        lang = "zh" if choice == "中文" else "en"
        if lang == "zh":
            return (lang,
                    gr.update(value="## 查询历史"),
                    gr.update(value="← 返回"),
                    gr.update(value="↻ 刷新"),
                    gr.update(value="✕ 删除所选"),
                    gr.update(value="清空全部"))
        return (lang,
                gr.update(value="## Query History"),
                gr.update(value="← Back"),
                gr.update(value="↻ Refresh"),
                gr.update(value="✕ Delete Selected"),
                gr.update(value="Clear All"))

    lang_dd.change(
        fn=_switch_lang,
        inputs=[lang_dd],
        outputs=[lang_state, title_md, back_btn, refresh_btn, delete_btn, clear_btn],
    )
    history_table.select(
        fn=_on_select,
        inputs=[selected_state],
        outputs=[selected_state, selected_info],
    )
    back_btn.click(fn=None, js="() => { window.location.href = '/text2sql'; }")
    refresh_btn.click(fn=_refresh, outputs=[history_table, selected_state, selected_info])
    delete_btn.click(
        fn=_delete_selected,
        inputs=[selected_state],
        outputs=[history_table, selected_state, selected_info],
    )
    clear_btn.click(fn=_clear, outputs=[history_table, selected_state, selected_info])


_HINTS_I18N: dict[str, list[str]] = {
    "en": [
        "Show all student information",
        "Top 3 students by score",
        "Total sales amount by city",
    ],
    "zh": [
        "查询所有学生信息",
        "成绩最高的3个学生",
        "每个城市的销售总额",
    ],
}


def _placeholder(lang: str = "en") -> str:
    hints = _HINTS_I18N.get(lang, _HINTS_I18N["en"])
    cards = "\n".join(f'<div class="st-hint-card">{h}</div>' for h in hints)
    title = _t2s(lang, "placeholder_title")
    return f'''<div class="st-empty-state">
  <div class="st-empty-logo" style="background:#0ea5e9;">SQL</div>
  <div class="st-empty-title">{title}</div>
  <div class="st-empty-hints">{cards}</div>
</div>'''


def render_text2sql_page(app=None) -> None:
    """Render the Text2SQL page components (call inside an app.route block)."""
    from dotenv import load_dotenv
    load_dotenv()

    lang = "en"
    t = lambda k: _t2s(lang, k)

    holder: dict[str, Any] = {
        "agent": None,
        "collector": None,
        "settings": None,
        "store": None,
        "full_store": None,
    }
    holder_lock = threading.Lock()

    def _table_choices(store, lang="zh"):
        """Build CheckboxGroup choices from a SchemaStore."""
        choices = []
        for tb in store.tables:
            if lang == "zh" and tb.comment:
                label = f"{tb.name} ({tb.comment})"
            else:
                label = tb.name
            choices.append(label)
        return choices

    def _sync_agent_store(new_store):
        """Update agent's runtime store AND rebuild its system prompt."""
        agent = holder.get("agent")
        if agent is not None:
            from .text2sql.prompts import build_text2sql_prompt
            agent.runtime.store = new_store
            agent._system_prompt = build_text2sql_prompt(new_store)
    logger = QueryLogger()

    env_hive = hive_config_from_env()

    with gr.Row(elem_classes=["st-page-row"]):
        lang_state = gr.State("en")

        # ── Left panel (sidebar) ──
        with gr.Column(scale=0, min_width=260, elem_classes=["st-sidebar"], elem_id="text2sql-sidebar") as sidebar_col:
            sidebar_toggle = gr.Button("☰", size="sm", elem_classes=["st-sidebar-toggle"])
            sidebar_title = gr.Markdown(t("sidebar_title"))
            schema_path_tb = gr.Textbox(
                label=t("schema_label"),
                value="",
                placeholder=schema_ddl_path_from_env(),
                elem_classes=["st-sidebar-control"],
            )
            hive_host_tb = gr.Textbox(
                label=t("hive_host"),
                value="",
                placeholder="10.0.0.1",
                elem_classes=["st-sidebar-control"],
            )
            with gr.Row(elem_classes=["st-sidebar-row"]):
                hive_port_tb = gr.Textbox(
                    label=t("port"),
                    value="",
                    placeholder="10000",
                    elem_classes=["st-sidebar-control"],
                )
                hive_db_tb = gr.Textbox(
                    label=t("database"),
                    value="",
                    placeholder="default",
                    elem_classes=["st-sidebar-control"],
                )
            connect_btn = gr.Button(t("connect"), variant="secondary", size="sm",
                                    elem_classes=["st-connect-btn"])
            reload_schema_btn = gr.Button(
                t("reload_schema"),
                size="sm",
                elem_classes=["st-connect-btn"],
            )
            with gr.Accordion(
                t("select_tables").format(n=0), open=False, visible=True,
                elem_classes=["st-filter-accordion"],
            ) as filter_accordion:
                table_search = gr.Textbox(
                    placeholder=t("search_placeholder"),
                    show_label=False, lines=1,
                    elem_classes=["st-table-search"],
                )
                table_filter = gr.CheckboxGroup(
                    choices=[], label="", show_label=False,
                    elem_classes=["st-table-filter"],
                )
                with gr.Row(elem_classes=["st-filter-actions"]):
                    select_all_btn = gr.Button(
                        t("select_all"), size="sm",
                        elem_classes=["st-filter-act-btn"],
                    )
                    deselect_all_btn = gr.Button(
                        t("deselect_all"), size="sm",
                        elem_classes=["st-filter-act-btn"],
                    )
                with gr.Row(elem_classes=["st-filter-confirm-row"]):
                    confirm_filter_btn = gr.Button(
                        f"✔ {t('confirm')}", variant="primary", size="sm",
                        elem_classes=["st-filter-confirm-btn"],
                    )
                    cancel_filter_btn = gr.Button(
                        f"✕ {t('cancel')}", size="sm",
                        elem_classes=["st-filter-cancel-btn"],
                    )
            status_box = gr.Textbox(label=t("status_label"), interactive=False,
                                    value=t("status_default"),
                                    elem_classes=["st-sidebar-status"])
            new_chat_btn = gr.Button(t("new_chat"), variant="primary", size="sm",
                                     elem_classes=["st-new-chat-btn"])
            export_btn = gr.DownloadButton(t("export_csv"), variant="secondary", size="sm",
                                           elem_classes=["st-connect-btn"])
            history_link = gr.Button(t("history"), variant="secondary", size="sm",
                                     elem_classes=["st-connect-btn"])
            history_link.click(fn=None, js="() => { window.location.href = '/history'; }")

        # ── Right panel (chat) ──
        with gr.Column(scale=1, elem_classes=["st-main"]):
            with gr.Row(elem_classes=["st-topbar-row"]):
                sidebar_open_btn = gr.Button("☰", size="sm", visible=False, elem_classes=["st-sidebar-open-btn"])
                gr.HTML('<div class="st-topbar-spacer"></div>')
                home_btn = gr.Button("\U0001f3e0", size="sm", elem_classes=["st-home-btn"])
                lang_dd = gr.Dropdown(
                    choices=["English", "中文"],
                    value="English",
                    show_label=False,
                    container=False,
                    min_width=140,
                    elem_classes=["st-lang-dd"],
                )

            chatbot = gr.Chatbot(
                show_label=False,
                placeholder=_placeholder(lang),
                layout="panel",
                buttons=["copy"],
                elem_classes=["st-chatbot"],
                height="calc(100vh - 130px)",
            )
            with gr.Row(elem_classes=["st-input-row"]):
                user_input = gr.Textbox(
                    placeholder=t("input_placeholder"),
                    show_label=False, scale=8, lines=1,
                    elem_classes=["st-input"],
                )
                send_btn = gr.Button("➤", variant="primary", size="sm", scale=0,
                                     min_width=48, elem_classes=["st-btn-send"])
                stop_btn = gr.Button("■", variant="stop", size="sm", scale=0,
                                     min_width=48, visible=False, elem_classes=["st-btn-stop"])

    # ── Sidebar toggle ──
    def _close_sidebar():
        return gr.update(visible=False), gr.update(visible=True)

    def _open_sidebar():
        return gr.update(visible=True), gr.update(visible=False)

    sidebar_toggle.click(fn=_close_sidebar, outputs=[sidebar_col, sidebar_open_btn])
    sidebar_open_btn.click(fn=_open_sidebar, outputs=[sidebar_col, sidebar_open_btn])

    # ── Callbacks ──

    def _connect(schema_path: str, host: str, port: str, db: str, lang: str):
        t = lambda k: _t2s(lang, k)
        no = gr.update()
        def err(msg):
            return (msg, no, no, no, no, no, no)
        try:
            settings = load_settings()
        except Exception as e:
            return err(f"❌ {t('llm_load_fail')}: {e}")

        # ── Resolve Hive config ──
        hive = None
        h = host.strip()
        p = port.strip()
        d = db.strip()
        if not h:
            fallback = hive_config_from_env()
            if fallback:
                h, p, d = fallback.host, str(fallback.port), fallback.database
        if h:
            try:
                hive = HiveConfig(
                    host=h,
                    port=int(p or "10000"),
                    database=d or "default",
                )
            except ValueError:
                return err(f"❌ {t('port_not_number')}")

        # ── Load schema: prefer Hive auto-fetch, DDL as optional whitelist ──
        store = None
        schema_source = ""
        ddl_path = schema_path.strip()

        if hive:
            from .text2sql.executor import HiveExecutor
            executor = HiveExecutor(hive)
            ok, msg = executor.test_connection()
            if not ok:
                return err(f"❌ Hive: {msg}")
            hive_note = f"✅ Hive {msg}"
            try:
                store = SchemaStore.from_hive(executor)
            except Exception as e:
                return err(f"❌ {t('schema_parse_fail')}: {e}")
            if ddl_path:
                ddl_file = Path(ddl_path)
                if ddl_file.is_file():
                    whitelist = SchemaStore.from_file(ddl_file)
                    wl_names = {n.lower() for n in whitelist.table_names}
                    filtered = [tb for tb in store.tables if tb.full_name.lower() in wl_names]
                    store = SchemaStore(filtered)
                    schema_source = t("loaded_tables").format(n=len(store)) + f" ({t('loaded_from_hive').format(n=len(whitelist), db=hive.database)} → whitelist)"
            if not schema_source:
                schema_source = t("loaded_from_hive").format(n=len(store), db=hive.database)
        else:
            hive_note = t("hive_not_configured")
            path = Path(ddl_path or schema_ddl_path_from_env())
            if not path.is_file():
                return err(f"❌ {t('schema_not_found')}: {path}")
            try:
                store = SchemaStore.from_file(path)
            except Exception as e:
                return err(f"❌ {t('schema_parse_fail')}: {e}")
            schema_source = t("loaded_tables").format(n=len(store))

        if len(store) == 0:
            return err(f"❌ {t('no_tables')}")

        with holder_lock:
            holder["settings"] = settings
            holder["store"] = store
            holder["full_store"] = store
            holder["hive"] = hive
            holder["agent"] = None
        status = f"✅ {schema_source} · {hive_note} · {t('model')} {settings.model_name}"

        choices = _table_choices(store, lang)
        return (
            status,
            gr.update(value=h),
            gr.update(value=p or "10000"),
            gr.update(value=d or "default"),
            gr.update(choices=choices, value=choices),
            gr.update(open=True, label=t("select_tables").format(n=len(store))),
            choices,
        )

    def _run_streaming(msg: str, history: list, lang: str):
        from .ui import EventCollector, _normalize_chat

        t = lambda k: _t2s(lang, k)
        history = _normalize_chat(history)
        collector = EventCollector()
        holder["collector"] = collector
        start = time.time()

        with holder_lock:
            if holder.get("agent") is None:
                from .text2sql.agent import Text2SQLAgent
                agent = Text2SQLAgent(
                    holder["settings"], store=holder["store"],
                    hive=holder.get("hive"), on_event=collector.on_event,
                )
                holder["agent"] = agent
                is_first = True
            else:
                agent = holder["agent"]
                agent._on_event = collector.on_event
                is_first = False

        error_msg = None

        def _worker():
            nonlocal error_msg
            try:
                if is_first:
                    agent.run(msg)
                else:
                    agent.chat(msg)
            except Exception as e:
                error_msg = str(e)
                collector.on_event("final_answer", {"text": f"Error: {e}"})

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        prev = 0
        while not collector.done:
            collector.wait_for_event(timeout=0.3)
            events = collector.snapshot()
            if len(events) > prev:
                prev = len(events)
                yield history + [{"role": "user", "content": msg}] + _format_events(events, start, lang)
        thread.join(timeout=5)
        final = _format_events(collector.snapshot(), start, lang)
        if error_msg:
            final.append({"role": "assistant", "content": f"⚠️ **Error**: {error_msg}"})
        final.append({"role": "assistant", "content": f"⏱️ {t('done')} {time.time() - start:.1f}s"})
        yield history + [{"role": "user", "content": msg}] + final

    def _handle_submit(msg: str, history: list, lang: str):
        t = lambda k: _t2s(lang, k)
        if not msg.strip():
            yield history
            return
        with holder_lock:
            store_ready = holder.get("store") is not None
        if not store_ready:
            yield history + [
                {"role": "user", "content": msg},
                {"role": "assistant", "content": t("connect_first")},
            ]
            return
        yield from _run_streaming(msg, history, lang)

    def _handle_stop(lang: str):
        t = lambda k: _t2s(lang, k)
        c = holder.get("collector")
        if c and not c.done:
            c.on_event("final_answer", {"text": t("stopped")})
        return gr.update(visible=True), gr.update(visible=False)

    def _new_chat():
        agent = holder.get("agent")
        if agent is not None:
            agent.reset()
        return []

    def _handle_export(lang: str):
        t = lambda k: _t2s(lang, k)
        agent = holder.get("agent")
        rt = agent.runtime if agent else None
        if rt is None or rt.last_result is None:
            raise gr.Error(t("no_export"))
        import tempfile
        from .text2sql.exporter import export_csv
        out_dir = Path(tempfile.gettempdir()) / "text2sql_exports"
        out_dir.mkdir(exist_ok=True)
        return export_csv(
            columns=rt.last_result.columns,
            rows=rt.last_result.rows,
            path=str(out_dir),
            name_hint="query_result",
        )

    def _reload_schema(ddl_path: str, lang: str):
        t = lambda k: _t2s(lang, k)
        no = gr.update()
        try:
            hive = holder.get("hive")
            if hive:
                from .text2sql.executor import HiveExecutor
                executor = HiveExecutor(hive)
                new_store = SchemaStore.from_hive(executor)
            else:
                from .text2sql.schema import parse_ddl
                path = Path(ddl_path or schema_ddl_path_from_env())
                if not path.is_file():
                    return f"❌ {t('schema_not_found')}: {path}", no, no, no
                text = path.read_text(encoding="utf-8")
                new_store = SchemaStore(parse_ddl(text))
            with holder_lock:
                holder["store"] = new_store
                holder["full_store"] = new_store
                _sync_agent_store(new_store)
            choices = _table_choices(new_store, lang)
            n = len(new_store)
            return (
                t("schema_reloaded").format(n=n),
                gr.update(choices=choices, value=choices),
                gr.update(open=True, label=t("select_tables").format(n=n)),
                choices,
            )
        except Exception as e:
            return f"Error: {e}", no, no, no

    def _apply_filter(selected: list, lang: str):
        t = lambda k: _t2s(lang, k)
        with holder_lock:
            full = holder.get("full_store")
        if not full:
            return t("status_default")
        if not selected:
            with holder_lock:
                holder["store"] = SchemaStore([])
                _sync_agent_store(holder["store"])
            return f"❌ {t('no_tables')}"
        sel_names = set()
        for label in selected:
            name = label.split("(")[0].strip()
            sel_names.add(name.lower())
        filtered = [tb for tb in full.tables if tb.name.lower() in sel_names]
        new_store = SchemaStore(filtered)
        with holder_lock:
            holder["store"] = new_store
            _sync_agent_store(new_store)
        n = len(new_store)
        total = len(full)
        if n == total:
            return f"✅ {t('select_tables').format(n=total)}"
        return f"✅ {t('filtered_tables').format(n=n)}"

    def _switch_lang(choice, cur_selected):
        lang = "zh" if choice == "中文" else "en"
        t = lambda k: _t2s(lang, k)
        full = holder.get("full_store")
        n = len(full) if full else 0
        # Rebuild choices with new lang; preserve selection by table name
        sel_names = set()
        for label in (cur_selected or []):
            sel_names.add(label.split("(")[0].strip().lower())
        choices = _table_choices(full, lang) if full else []
        new_selected = [c for c in choices if c.split("(")[0].strip().lower() in sel_names]
        return (
            lang,
            gr.update(value=t("sidebar_title")),
            gr.update(label=t("schema_label")),
            gr.update(label=t("hive_host")),
            gr.update(label=t("port")),
            gr.update(label=t("database")),
            gr.update(value=t("connect")),
            gr.update(label=t("status_label")),
            gr.update(value=t("new_chat")),
            gr.update(label=t("export_csv")),
            gr.update(value=t("history")),
            gr.update(placeholder=t("input_placeholder")),
            gr.update(placeholder=_placeholder(lang)),
            gr.update(value=t("reload_schema")),
            gr.update(label=t("select_tables").format(n=n)),  # accordion
            gr.update(value=t("select_all")),
            gr.update(value=t("deselect_all")),
            gr.update(value=f"✔ {t('confirm')}"),
            gr.update(value=f"✕ {t('cancel')}"),
            gr.update(placeholder=t("search_placeholder")),
            gr.update(choices=choices, value=new_selected),
        )

    # ── Wiring ──
    confirmed_sel = gr.State([])

    lang_dd.change(
        fn=_switch_lang,
        inputs=[lang_dd, table_filter],
        outputs=[
            lang_state,
            sidebar_title,
            schema_path_tb,
            hive_host_tb,
            hive_port_tb,
            hive_db_tb,
            connect_btn,
            status_box,
            new_chat_btn,
            export_btn,
            history_link,
            user_input,
            chatbot,
            reload_schema_btn,
            filter_accordion,
            select_all_btn,
            deselect_all_btn,
            confirm_filter_btn,
            cancel_filter_btn,
            table_search,
            table_filter,
        ],
    )

    connect_btn.click(
        fn=_connect,
        inputs=[schema_path_tb, hive_host_tb, hive_port_tb, hive_db_tb, lang_state],
        outputs=[status_box, hive_host_tb, hive_port_tb, hive_db_tb,
                 table_filter, filter_accordion, confirmed_sel],
    )

    def _show_stop():
        return gr.update(visible=False), gr.update(visible=True)

    def _post_submit():
        return "", gr.update(visible=True), gr.update(visible=False)

    submit_io = dict(fn=_handle_submit, inputs=[user_input, chatbot, lang_state], outputs=chatbot)
    send_btn.click(fn=_show_stop, outputs=[send_btn, stop_btn]) \
        .then(**submit_io) \
        .then(fn=_post_submit, outputs=[user_input, send_btn, stop_btn])
    user_input.submit(fn=_show_stop, outputs=[send_btn, stop_btn]) \
        .then(**submit_io) \
        .then(fn=_post_submit, outputs=[user_input, send_btn, stop_btn])

    stop_btn.click(fn=_handle_stop, inputs=[lang_state], outputs=[send_btn, stop_btn])
    new_chat_btn.click(fn=_new_chat, outputs=chatbot)
    export_btn.click(fn=_handle_export, inputs=[lang_state], outputs=export_btn)
    reload_schema_btn.click(fn=_reload_schema, inputs=[schema_path_tb, lang_state],
                            outputs=[status_box, table_filter, filter_accordion, confirmed_sel])

    def _select_all(lang):
        with holder_lock:
            full = holder.get("full_store")
        if not full:
            return gr.update()
        return gr.update(value=_table_choices(full, lang))

    def _deselect_all():
        return gr.update(value=[])

    def _confirm_filter(selected, lang):
        t = lambda k: _t2s(lang, k)
        status = _apply_filter(selected, lang)
        n = len(selected)
        return status, list(selected), gr.update(label=t("select_tables").format(n=n))

    def _cancel_filter(prev):
        return gr.update(value=prev)

    select_all_btn.click(fn=_select_all, inputs=[lang_state], outputs=[table_filter])
    deselect_all_btn.click(fn=_deselect_all, outputs=[table_filter])
    confirm_filter_btn.click(
        fn=_confirm_filter, inputs=[table_filter, lang_state],
        outputs=[status_box, confirmed_sel, filter_accordion],
    )
    cancel_filter_btn.click(
        fn=_cancel_filter, inputs=[confirmed_sel],
        outputs=[table_filter],
    )

    _search_js = """
    (q) => {
        const el = document.querySelector('.st-table-filter');
        if (!el) return q;
        const labels = el.querySelectorAll('label');
        const low = (q || '').toLowerCase();
        labels.forEach(lb => {
            lb.style.display = lb.textContent.toLowerCase().includes(low) ? '' : 'none';
        });
        return q;
    }
    """
    table_search.input(fn=None, js=_search_js, inputs=[table_search], outputs=[table_search])

    # ── Home button ──
    home_btn.click(fn=None, js="() => { window.location.href = '/'; }")

    # ── Force sidebar column layout (Gradio 6.x internal divs override CSS) ──
    _sidebar_fix_js = """() => {
        function fixSidebar() {
            const sb = document.querySelector('.st-sidebar');
            if (!sb) return;
            sb.style.setProperty('display', 'flex', 'important');
            sb.style.setProperty('flex-direction', 'column', 'important');
            sb.style.setProperty('flex-wrap', 'nowrap', 'important');
            const allDivs = sb.querySelectorAll('div');
            for (const el of allDivs) {
                const cl = el.className || '';
                // Skip explicit Row containers
                if (cl.includes('row') || cl.includes('st-filter-actions') ||
                    cl.includes('st-filter-confirm') || cl.includes('st-action-row') ||
                    cl.includes('st-rename-row') || cl.includes('st-topbar')) continue;
                // Skip CheckboxGroup label wrappers (they need column from CSS)
                if (el.closest('.st-table-filter') && el.classList.contains('wrap')) {
                    el.style.setProperty('flex-direction', 'column', 'important');
                    el.style.setProperty('flex-wrap', 'nowrap', 'important');
                    continue;
                }
                el.style.setProperty('display', 'flex', 'important');
                el.style.setProperty('flex-direction', 'column', 'important');
                el.style.setProperty('flex-wrap', 'nowrap', 'important');
                el.style.setProperty('width', '100%', 'important');
                el.style.setProperty('max-width', '100%', 'important');
                el.style.setProperty('min-width', '0', 'important');
            }
        }
        fixSidebar();
        setTimeout(fixSidebar, 200);
        setTimeout(fixSidebar, 1000);
        let tid;
        new MutationObserver(() => {
            clearTimeout(tid);
            tid = setTimeout(fixSidebar, 80);
        }).observe(document.body, {childList: true, subtree: true});
    }"""

    # ── Clickable hint cards (event delegation — works after language switch) ──
    _hint_delegate_js = """() => {
        if (document._hintDelegated) return;
        document._hintDelegated = true;
        document.addEventListener('click', e => {
            const card = e.target.closest('.st-hint-card');
            if (!card) return;
            const ta = document.querySelector('.st-input textarea');
            if (ta) {
                const nativeSetter = Object.getOwnPropertyDescriptor(
                    HTMLTextAreaElement.prototype, 'value').set;
                nativeSetter.call(ta, card.textContent.trim());
                ta.dispatchEvent(new Event('input', {bubbles: true}));
            }
        });
    }"""
    if app is not None:
        app.load(fn=None, js=_sidebar_fix_js)
        app.load(fn=None, js=_hint_delegate_js)
