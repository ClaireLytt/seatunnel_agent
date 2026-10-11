# -*- coding: utf-8 -*-
"""Gradio page for the metric consistency checker.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Metric Diff", "/metricdiff")``.  Fully deterministic —
column-lineage expression comparison, nothing executed.
"""

from __future__ import annotations

import gradio as gr

from .metric_diff import check_sql_dir, render_markdown
from .metric_diff.i18n import normalize_lang

_DIALECTS = ["hive", "spark", "mysql", "postgresql", "clickhouse",
             "doris", "starrocks"]

_I18N = {
    "en": {
        "title": "## 📏 Metric Consistency Check\n"
                 "Find same-named output columns DEFINED differently across "
                 "jobs — the number-one reason two reports disagree. "
                 "Expressions are canonicalized before comparing, so "
                 "formatting differences never flag. No database, no LLM.",
        "dir_label": "SQL directory",
        "dir_ph": "Directory containing *.sql (scanned recursively), "
                  "e.g. examples/metricdiff_demo",
        "dialect_label": "SQL dialect",
        "check_btn": "Check metrics",
        "empty_dir": "⚠️ Provide a SQL directory first.",
        "bad_dir": "⚠️ Not a directory: ",
    },
    "zh": {
        "title": "## 📏 指标口径一致性检查\n"
                 "找出不同作业里同名但定义不同的输出列 — 「两张报表数对"
                 "不上」的头号原因。表达式先归一化再比较，排版差异不会误报。"
                 "不连数据库、不调用 LLM。",
        "dir_label": "SQL 目录",
        "dir_ph": "包含 *.sql 的目录（递归扫描），如 examples/metricdiff_demo",
        "dialect_label": "SQL 方言",
        "check_btn": "检查口径",
        "empty_dir": "⚠️ 请先填写 SQL 目录。",
        "bad_dir": "⚠️ 不是有效目录: ",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_metric_diff_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-mdf-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-mdf-side"]):
                dir_box = gr.Textbox(
                    label=t("dir_label"), placeholder=t("dir_ph"),
                    value="examples/metricdiff_demo")
                dialect_dd = gr.Dropdown(
                    choices=_DIALECTS, value="hive",
                    label=t("dialect_label"))
                check_btn = gr.Button(t("check_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-mdf-main"]):
                report_md = gr.Markdown("")

    # ── callbacks ──

    def do_check(dir_text: str, dialect: str, lang: str):
        from pathlib import Path
        lang = normalize_lang(lang)
        if not (dir_text or "").strip():
            return _t(lang, "empty_dir")
        if not Path(dir_text.strip()).is_dir():
            return _t(lang, "bad_dir") + dir_text
        try:
            report = check_sql_dir(dir_text.strip(), dialect=dialect)
        except Exception as exc:  # noqa: BLE001 — check must never crash the page
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
            gr.update(value=_t(lang, "check_btn")),
        )

    check_btn.click(
        do_check,
        inputs=[dir_box, dialect_dd, lang_state],
        outputs=[report_md],
    )

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, dir_box, dialect_dd, check_btn],
    )
