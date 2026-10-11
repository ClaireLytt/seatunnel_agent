# -*- coding: utf-8 -*-
"""Gradio page for the SQL formatter.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("SQL Format", "/sqlfmt")``.  Fully deterministic — statements
that do not parse are kept verbatim. The UI is check-only: writing files
back is a CLI affair (``seatunnel-agent sqlfmt --write``).
"""

from __future__ import annotations

import gradio as gr

from .sql_fmt import fmt_dir, format_text, render_batch_markdown, render_markdown
from .sql_fmt.i18n import normalize_lang

_DIALECTS = ["hive", "spark", "mysql", "postgresql", "clickhouse",
             "doris", "starrocks"]

_I18N = {
    "en": {
        "title": "## 🪄 SQL Formatter\n"
                 "Deterministic sqlglot pretty-print with a black-style "
                 "workflow — format pasted SQL, or check a directory for "
                 "files that would be reformatted. Statements that do not "
                 "parse are kept verbatim; the UI never writes files "
                 "(use the CLI's --write).",
        "sql_label": "SQL input",
        "sql_ph": "Paste one or more ;-separated statements…",
        "dialect_label": "SQL dialect",
        "fmt_btn": "Format",
        "dir_acc": "Check a directory",
        "dir_label": "SQL directory",
        "dir_ph": "Directory containing *.sql (scanned recursively), "
                  "e.g. examples/sqlfmt_demo",
        "dir_btn": "Check directory",
        "empty_sql": "⚠️ Paste some SQL first.",
        "empty_dir": "⚠️ Provide a SQL directory first.",
        "bad_dir": "⚠️ Not a directory: ",
    },
    "zh": {
        "title": "## 🪄 SQL 格式化\n"
                 "基于 sqlglot 的确定性格式化，black 式工作流 — 粘贴 SQL "
                 "直接格式化，或检查目录里哪些文件需要重排。解析失败的语句"
                 "原样保留；页面只做检查不写文件（写回用 CLI 的 --write）。",
        "sql_label": "SQL 输入",
        "sql_ph": "粘贴一条或多条以 ; 分隔的 SQL…",
        "dialect_label": "SQL 方言",
        "fmt_btn": "格式化",
        "dir_acc": "检查目录",
        "dir_label": "SQL 目录",
        "dir_ph": "包含 *.sql 的目录（递归扫描），如 examples/sqlfmt_demo",
        "dir_btn": "检查目录",
        "empty_sql": "⚠️ 请先粘贴 SQL。",
        "empty_dir": "⚠️ 请先填写 SQL 目录。",
        "bad_dir": "⚠️ 不是有效目录: ",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_sql_fmt_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-fmt-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-fmt-side"]):
                sql_box = gr.Textbox(
                    label=t("sql_label"), placeholder=t("sql_ph"), lines=12)
                dialect_dd = gr.Dropdown(
                    choices=_DIALECTS, value="hive",
                    label=t("dialect_label"))
                fmt_btn = gr.Button(t("fmt_btn"), variant="primary")
                with gr.Accordion(t("dir_acc"), open=False) as dir_acc:
                    dir_box = gr.Textbox(
                        label=t("dir_label"), placeholder=t("dir_ph"),
                        value="examples/sqlfmt_demo")
                    dir_btn = gr.Button(t("dir_btn"))

            with gr.Column(scale=5, elem_classes=["st-fmt-main"]):
                report_md = gr.Markdown("")

    # ── callbacks ──

    def do_format(sql_text: str, dialect: str, lang: str):
        lang = normalize_lang(lang)
        if not (sql_text or "").strip():
            return _t(lang, "empty_sql")
        try:
            return render_markdown(format_text(sql_text, dialect=dialect),
                                   lang)
        except Exception as exc:  # noqa: BLE001 — format must never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"

    def do_check_dir(dir_text: str, dialect: str, lang: str):
        from pathlib import Path
        lang = normalize_lang(lang)
        if not (dir_text or "").strip():
            return _t(lang, "empty_dir")
        if not Path(dir_text.strip()).is_dir():
            return _t(lang, "bad_dir") + dir_text
        try:
            results = fmt_dir(dir_text.strip(), dialect=dialect, write=False)
            return render_batch_markdown(results, lang)
        except Exception as exc:  # noqa: BLE001
            return f"⚠️ {type(exc).__name__}: {exc}"

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "sql_label"),
                      placeholder=_t(lang, "sql_ph")),
            gr.update(label=_t(lang, "dialect_label")),
            gr.update(value=_t(lang, "fmt_btn")),
            gr.update(label=_t(lang, "dir_acc")),
            gr.update(label=_t(lang, "dir_label"),
                      placeholder=_t(lang, "dir_ph")),
            gr.update(value=_t(lang, "dir_btn")),
        )

    fmt_btn.click(do_format, inputs=[sql_box, dialect_dd, lang_state],
                  outputs=[report_md])
    dir_btn.click(do_check_dir, inputs=[dir_box, dialect_dd, lang_state],
                  outputs=[report_md])

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, sql_box, dialect_dd, fmt_btn,
                 dir_acc, dir_box, dir_btn],
    )
