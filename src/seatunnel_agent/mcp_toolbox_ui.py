# -*- coding: utf-8 -*-
"""Read-only showcase/status page for the MCP toolbox (``/mcp``).

The toolbox itself is a stdio server for external MCP clients — this page
makes it discoverable from the hub: what tools exist, how to wire a client,
which safety switches to use, and an audit panel over
``logs/mcp_toolbox.jsonl`` showing what external AIs actually called.
"""

from __future__ import annotations

import json

import gradio as gr

from .mcp_toolbox import _audit_file, build_tool_functions

_DEFAULT_LANG = "en"

_I18N: dict[str, dict[str, str]] = {
    "en": {
        "title": "## 🧰 MCP Toolbox",
        "subtitle": (
            "The whole agent suite as one stdio MCP server for Claude Code / "
            "Claude Desktop / Cline / Cursor. Deterministic tools only — no "
            "LLM calls inside; database access goes through NAMED saved "
            "connections (credentials never enter the model context)."
        ),
        "tools_head": "### Tools",
        "tools_note": (
            "*Lineage tools (7 more) and `data_dictionary` load when the "
            "server is started with `--sql-dir` / `--seatunnel-dir` / "
            "`--hive`. Safety switches: `--no-db` (pure-static profile), "
            "`--connections a,b` (allowlist), "
            "`SEATUNNEL_MCP_QUERY_TIMEOUT` (default 60s).*"
        ),
        "col_tool": "Tool",
        "col_desc": "What it does",
        "setup_head": "### Client setup",
        "setup_code_label": "Claude Code",
        "desktop_code_label": "Claude Desktop (claude_desktop_config.json)",
        "audit_head": "### Call audit (logs/mcp_toolbox.jsonl)",
        "audit_refresh": "Refresh",
        "audit_empty": "*No MCP tool calls recorded yet.*",
        "a_time": "Time", "a_tool": "Tool", "a_ok": "OK",
        "a_ms": "ms", "a_args": "Args",
        "audit_total": "{n} calls · {ok} ok · {fail} failed",
    },
    "zh": {
        "title": "## 🧰 MCP 工具箱",
        "subtitle": (
            "把整套 agent 以一个 stdio MCP server 交给 Claude Code / "
            "Claude Desktop / Cline / Cursor。全部工具确定性实现——内部不调用 "
            "LLM；数据库访问按**连接名**引用已保存连接，凭据不进模型上下文。"
        ),
        "tools_head": "### 工具清单",
        "tools_note": (
            "*血缘工具（另外 7 个）与 `data_dictionary` 在启动时给出 "
            "`--sql-dir` / `--seatunnel-dir` / `--hive` 后加载。安全开关："
            "`--no-db`（纯静态模式）、`--connections a,b`（连接白名单）、"
            "`SEATUNNEL_MCP_QUERY_TIMEOUT`（查询超时，默认 60s）。*"
        ),
        "col_tool": "工具",
        "col_desc": "说明",
        "setup_head": "### 客户端接入",
        "setup_code_label": "Claude Code",
        "desktop_code_label": "Claude Desktop（claude_desktop_config.json）",
        "audit_head": "### 调用审计（logs/mcp_toolbox.jsonl）",
        "audit_refresh": "刷新",
        "audit_empty": "*暂无 MCP 工具调用记录。*",
        "a_time": "时间", "a_tool": "工具", "a_ok": "结果",
        "a_ms": "耗时(ms)", "a_args": "参数",
        "audit_total": "共 {n} 次调用 · 成功 {ok} · 失败 {fail}",
    },
}

# one-line bilingual descriptions per tool (the docstrings are zh-first;
# the page needs clean copy in both languages)
_TOOL_DESC: dict[str, dict[str, str]] = {
    "sql_review": {"zh": "SQL 静态审查：性能/质量/规范规则，严重度分级报告",
                   "en": "Static SQL review: perf/quality rules, severity-graded report"},
    "sql_transpile": {"zh": "方言翻译 + 不兼容点清单（确定性，不执行 SQL）",
                      "en": "Dialect translation + incompatibility report (deterministic)"},
    "skew_check": {"zh": "数据倾斜静态分析（DS001–DS013）",
                   "en": "Static data-skew scan (rules DS001–DS013)"},
    "skew_check_file": {"zh": "对一个 SQL 文件做倾斜静态分析",
                        "en": "Skew scan over a SQL file"},
    "skew_verify": {"zh": "连库实测验证倾斜：键值分布探针 + 热点值 + 改写模板",
                    "en": "Live skew verification: key-distribution probes, hot values, rewrite templates"},
    "impact_diff": {"zh": "两段 SQL 的变更影响面（表/字段级 diff + 严重度）",
                    "en": "Change-impact blast radius between two SQL snippets"},
    "migrate_to_seatunnel": {"zh": "DataX JSON / sqoop 命令 → SeaTunnel 配置",
                             "en": "DataX JSON / sqoop command → SeaTunnel config"},
    "list_saved_connections": {"zh": "列出已保存连接（不含凭据）",
                               "en": "List saved connections (no credentials)"},
    "list_tables": {"zh": "列出连接中的表（子串过滤）",
                    "en": "List tables on a connection (substring filter)"},
    "table_schema": {"zh": "表结构：列/类型/注释/分区列",
                     "en": "Table schema: columns/types/comments/partitions"},
    "run_query": {"zh": "只读查询：单条 SELECT/WITH，≤500 行 + 引擎侧 LIMIT",
                  "en": "Read-only query: single SELECT/WITH, ≤500 rows + engine-side LIMIT"},
    "compare_row_count": {"zh": "跨库行数比对（可加 where）",
                          "en": "Cross-database row-count compare (optional where)"},
    "compare_schema": {"zh": "跨库结构比对：独有列 + 类型差异",
                       "en": "Cross-database schema compare: missing columns + type drift"},
    "compare_checksum": {"zh": "跨库分段校验和比对（同名列交集）",
                         "en": "Cross-database segmented checksum compare"},
    "compare_query_results": {"zh": "一致性实测：两版 SQL 结果等价性验证",
                              "en": "Consistency measurement: verify two SQLs return equal results"},
}

_SETUP_BASH = """pip install 'seatunnel-agent[mcp]'
seatunnel-agent mcp                          # 15 tools
seatunnel-agent mcp --no-db                  # pure-static (6 tools)
seatunnel-agent mcp --connections dev,stage  # connection allowlist
claude mcp add seatunnel-agent -- seatunnel-agent mcp"""

_SETUP_JSON = """{
  "mcpServers": {
    "seatunnel-agent": {
      "command": "seatunnel-agent",
      "args": ["mcp", "--sql-dir", "D:/warehouse/sql"]
    }
  }
}"""


def _ut(lang: str, key: str) -> str:
    return _I18N.get(lang, _I18N["en"]).get(key, key)


def _tools_md(lang: str) -> str:
    t = lambda k: _ut(lang, k)  # noqa: E731
    names = list(build_tool_functions(include_db=True))
    lines = [t("tools_head"), "",
             f"| {t('col_tool')} | {t('col_desc')} |", "|---|---|"]
    for name in names:
        desc = _TOOL_DESC.get(name, {}).get(lang, "")
        lines.append(f"| `{name}` | {desc} |")
    lines += ["", t("tools_note")]
    return "\n".join(lines)


def _audit_md(lang: str) -> str:
    t = lambda k: _ut(lang, k)  # noqa: E731
    try:
        raw = _audit_file().read_text(encoding="utf-8").splitlines()
    except OSError:
        return t("audit_empty")
    records = []
    for line in raw:
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    if not records:
        return t("audit_empty")
    ok = sum(1 for r in records if r.get("ok"))
    lines = [t("audit_total").format(n=len(records), ok=ok,
                                     fail=len(records) - ok), "",
             f"| {t('a_time')} | {t('a_tool')} | {t('a_ok')} "
             f"| {t('a_ms')} | {t('a_args')} |",
             "|---|---|---|---|---|"]
    for r in records[-20:][::-1]:
        mark = "✅" if r.get("ok") else "⛔"
        args = str(r.get("args", "")).replace("|", "\\|")[:60]
        lines.append(
            f"| {str(r.get('timestamp', ''))[:19]} | `{r.get('tool', '')}` "
            f"| {mark} | {r.get('elapsed_ms', 0)} | `{args}` |")
    return "\n".join(lines)


def render_mcp_page(app: gr.Blocks) -> None:
    t0 = lambda k: _ut(_DEFAULT_LANG, k)  # noqa: E731 — initial labels

    # markers: page scroll (shared CSS) + uitest READY selector
    gr.HTML('<div class="st-scroll-page st-mcp-page" style="display:none"></div>')

    with gr.Row():
        title_md = gr.Markdown(f"{t0('title')}\n{t0('subtitle')}")
        home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                             elem_classes=["st-home-btn"])
    lang_state = gr.State(_DEFAULT_LANG)

    with gr.Row():
        with gr.Column(scale=3):
            tools_md = gr.Markdown(_tools_md(_DEFAULT_LANG),
                                   elem_classes=["st-mcp-tools"])
        with gr.Column(scale=2):
            setup_md = gr.Markdown(t0("setup_head"))
            setup_code = gr.Code(value=_SETUP_BASH, language="shell",
                                 label=t0("setup_code_label"),
                                 buttons=["copy"], lines=5)
            desktop_code = gr.Code(value=_SETUP_JSON, language="json",
                                   label=t0("desktop_code_label"),
                                   buttons=["copy"], lines=8)
            with gr.Row():
                audit_head_md = gr.Markdown(t0("audit_head"))
                audit_refresh_btn = gr.Button(t0("audit_refresh"), size="sm",
                                              scale=0)
            audit_md = gr.Markdown(t0("audit_empty"))

    def do_audit_refresh(lang: str) -> str:
        return _audit_md(lang)

    audit_refresh_btn.click(do_audit_refresh, inputs=[lang_state],
                            outputs=[audit_md])

    def _switch_lang(choice: str):
        lg = "zh" if choice == "中文" else "en"
        t = lambda k: _ut(lg, k)  # noqa: E731
        return (
            lg,                                          # lang_state
            f"{t('title')}\n{t('subtitle')}",            # title_md
            _tools_md(lg),                               # tools_md
            t("setup_head"),                             # setup_md
            gr.update(label=t("setup_code_label")),      # setup_code
            gr.update(label=t("desktop_code_label")),    # desktop_code
            t("audit_head"),                             # audit_head_md
            gr.update(value=t("audit_refresh")),         # audit_refresh_btn
            _audit_md(lg),                               # audit_md
        )

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return _switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load,
        inputs=None,
        outputs=[lang_state, title_md, tools_md, setup_md, setup_code,
                 desktop_code, audit_head_md, audit_refresh_btn, audit_md],
    )
