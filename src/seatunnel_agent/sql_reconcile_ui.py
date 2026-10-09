# -*- coding: utf-8 -*-
"""Gradio page for the SQL caliber reconciliation agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Reconcile", "/reconcile")``.  Fully deterministic —
no database, no LLM, nothing executed; AST diff of two SQL statements.
"""

from __future__ import annotations

import gradio as gr

from .sql_reconcile import reconcile_sql, render_markdown
from .sql_reconcile.i18n import normalize_lang

_DIALECTS = ["hive", "spark", "mysql", "postgresql", "clickhouse",
             "doris", "starrocks"]

_I18N = {
    "en": {
        "title": "## ⚖️ SQL Caliber Reconciliation\n"
                 "Two reports disagree on the same number? Paste both SQL "
                 "statements and get an AST-level explanation of why — "
                 "different filters, join types, time ranges, dedup or "
                 "aggregation calibers. No database connection, nothing "
                 "executed.",
        "dialect_label": "SQL dialect",
        "a_label": "SQL A",
        "a_ph": "Paste the first SQL…",
        "b_label": "SQL B",
        "b_ph": "Paste the second SQL…",
        "diff_btn": "Reconcile",
        "empty_sql": "⚠️ Paste both SQL statements first.",
    },
    "zh": {
        "title": "## ⚖️ SQL 口径对账\n"
                 "两个报表的同一个数字对不上？粘贴两条 SQL，AST 级对比给出"
                 "原因 — 过滤条件、JOIN 类型、时间范围、去重或聚合口径的"
                 "差异。不连接数据库、不执行任何语句。",
        "dialect_label": "SQL 方言",
        "a_label": "SQL A",
        "a_ph": "粘贴第一条 SQL…",
        "b_label": "SQL B",
        "b_ph": "粘贴第二条 SQL…",
        "diff_btn": "对账",
        "empty_sql": "⚠️ 请先粘贴两条 SQL。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_sql_reconcile_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-rec-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-rec-side"]):
                dialect_dd = gr.Dropdown(
                    choices=_DIALECTS, value="hive",
                    label=t("dialect_label"))
                a_box = gr.Textbox(
                    label=t("a_label"), placeholder=t("a_ph"), lines=8)
                b_box = gr.Textbox(
                    label=t("b_label"), placeholder=t("b_ph"), lines=8)
                diff_btn = gr.Button(t("diff_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-rec-main"]):
                report_md = gr.Markdown("")

    # ── callbacks ──

    def do_reconcile(sql_a: str, sql_b: str, dialect: str, lang: str):
        lang = normalize_lang(lang)
        if not (sql_a or "").strip() or not (sql_b or "").strip():
            return _t(lang, "empty_sql")
        try:
            report = reconcile_sql(sql_a, sql_b, dialect=dialect)
        except Exception as exc:  # noqa: BLE001 — diff must never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"
        return render_markdown(report, lang)

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "dialect_label")),
            gr.update(label=_t(lang, "a_label"),
                      placeholder=_t(lang, "a_ph")),
            gr.update(label=_t(lang, "b_label"),
                      placeholder=_t(lang, "b_ph")),
            gr.update(value=_t(lang, "diff_btn")),
        )

    diff_btn.click(
        do_reconcile,
        inputs=[a_box, b_box, dialect_dd, lang_state],
        outputs=[report_md],
    )

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, dialect_dd, a_box, b_box, diff_btn],
    )
