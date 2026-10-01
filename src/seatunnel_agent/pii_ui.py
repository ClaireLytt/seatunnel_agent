# -*- coding: utf-8 -*-
"""Gradio page for the PII / sensitive-column scan agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("PII Scan", "/pii")``.  Fully deterministic — no database, no
LLM, nothing executed; scans SQL files (or pasted SQL) only.
"""

from __future__ import annotations

import gradio as gr

from .pii_scan import render_markdown, scan_dir, scan_sql_text
from .pii_scan.i18n import normalize_lang

_DIALECTS = ["hive", "spark", "mysql", "postgresql", "clickhouse",
             "doris", "starrocks"]

_I18N = {
    "en": {
        "title": "## 🔒 PII / Sensitive Column Scan\n"
                 "Naming rules × column lineage — find sensitive columns in "
                 "SQL files and trace where they spread downstream, flagging "
                 "unmasked propagation. No database connection, nothing "
                 "executed.",
        "dir_label": "SQL directory",
        "dir_ph": "Directory containing *.sql files (scanned recursively), "
                  "e.g. examples/pii_demo",
        "dialect_label": "SQL dialect",
        "scan_btn": "Scan directory",
        "inline_acc": "Scan pasted SQL",
        "sql_label": "SQL input",
        "sql_ph": "Paste CREATE TABLE / INSERT ... SELECT statements…",
        "scan_sql_btn": "Scan SQL",
        "result_label": "Scan report",
        "empty_dir": "⚠️ Provide a SQL directory first.",
        "bad_dir": "⚠️ Not a directory: ",
        "empty_sql": "⚠️ Paste some SQL first.",
    },
    "zh": {
        "title": "## 🔒 敏感数据扫描 (PII)\n"
                 "命名规则 × 字段血缘 — 在 SQL 文件中识别敏感列，并沿血缘追踪"
                 "下游扩散，标出未脱敏的传播路径。不连接数据库、不执行任何语句。",
        "dir_label": "SQL 目录",
        "dir_ph": "包含 *.sql 的目录（递归扫描），如 examples/pii_demo",
        "dialect_label": "SQL 方言",
        "scan_btn": "扫描目录",
        "inline_acc": "扫描粘贴的 SQL",
        "sql_label": "SQL 输入",
        "sql_ph": "粘贴 CREATE TABLE / INSERT ... SELECT 语句…",
        "scan_sql_btn": "扫描 SQL",
        "result_label": "扫描报告",
        "empty_dir": "⚠️ 请先填写 SQL 目录。",
        "bad_dir": "⚠️ 不是有效目录: ",
        "empty_sql": "⚠️ 请先粘贴 SQL。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_pii_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-pii-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-pii-side"]):
                dir_box = gr.Textbox(
                    label=t("dir_label"), placeholder=t("dir_ph"),
                    value="examples/pii_demo")
                dialect_dd = gr.Dropdown(
                    choices=_DIALECTS, value="hive",
                    label=t("dialect_label"))
                scan_btn = gr.Button(t("scan_btn"), variant="primary")
                with gr.Accordion(t("inline_acc"), open=False) as inline_acc:
                    sql_box = gr.Textbox(
                        label=t("sql_label"), placeholder=t("sql_ph"),
                        lines=8)
                    scan_sql_btn = gr.Button(t("scan_sql_btn"))

            with gr.Column(scale=5, elem_classes=["st-pii-main"]):
                report_md = gr.Markdown("")

    # ── callbacks ──

    def do_scan_dir(dir_text: str, dialect: str, lang: str):
        from pathlib import Path
        lang = normalize_lang(lang)
        if not (dir_text or "").strip():
            return _t(lang, "empty_dir")
        if not Path(dir_text.strip()).is_dir():
            return _t(lang, "bad_dir") + dir_text
        try:
            report = scan_dir(dir_text.strip(), dialect=dialect)
        except Exception as exc:  # noqa: BLE001 — scan must never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"
        return render_markdown(report, lang)

    def do_scan_sql(sql_text: str, dialect: str, lang: str):
        lang = normalize_lang(lang)
        if not (sql_text or "").strip():
            return _t(lang, "empty_sql")
        try:
            report = scan_sql_text(sql_text, dialect=dialect)
        except Exception as exc:  # noqa: BLE001
            return f"⚠️ {type(exc).__name__}: {exc}"
        return render_markdown(report, lang)

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "dir_label"),
                      placeholder=_t(lang, "dir_ph")),
            gr.update(label=_t(lang, "dialect_label")),
            gr.update(value=_t(lang, "scan_btn")),
            gr.update(label=_t(lang, "inline_acc")),
            gr.update(label=_t(lang, "sql_label"),
                      placeholder=_t(lang, "sql_ph")),
            gr.update(value=_t(lang, "scan_sql_btn")),
        )

    scan_btn.click(
        do_scan_dir,
        inputs=[dir_box, dialect_dd, lang_state],
        outputs=[report_md],
    )
    scan_sql_btn.click(
        do_scan_sql,
        inputs=[sql_box, dialect_dd, lang_state],
        outputs=[report_md],
    )

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, dir_box, dialect_dd, scan_btn,
                 inline_acc, sql_box, scan_sql_btn],
    )
