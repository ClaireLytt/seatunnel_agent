# -*- coding: utf-8 -*-
"""Gradio page for the scheduling DAG health checker.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("DAG Check", "/dagcheck")``.  Fully deterministic — graph
analysis over SQL/SeaTunnel lineage, nothing executed.
"""

from __future__ import annotations

import gradio as gr

from .dag_check import check_sql_dir, render_markdown
from .dag_check.i18n import normalize_lang

_DIALECTS = ["hive", "spark", "mysql", "postgresql", "clickhouse",
             "doris", "starrocks"]

_I18N = {
    "en": {
        "title": "## 🗓️ Scheduling DAG Health Check\n"
                 "Build the job DAG from SQL lineage and report what breaks "
                 "a scheduler — cycles, mid-layer tables nobody produces or "
                 "consumes — plus execution batches and the critical path. "
                 "No scheduler connection, nothing executed.",
        "dir_label": "SQL directory",
        "dir_ph": "Directory containing *.sql (scanned recursively), "
                  "e.g. examples/dagcheck_demo",
        "st_label": "SeaTunnel config directory (optional)",
        "st_ph": "Merge source→sink lineage from *.conf files",
        "dialect_label": "SQL dialect",
        "check_btn": "Check DAG",
        "empty_dir": "⚠️ Provide a SQL directory first.",
        "bad_dir": "⚠️ Not a directory: ",
    },
    "zh": {
        "title": "## 🗓️ 调度 DAG 体检\n"
                 "从 SQL 血缘构建作业 DAG，报告会卡住调度器的问题 — "
                 "依赖成环、没人产出/没人消费的中间层表 — 并给出执行分批"
                 "与关键路径。不连接调度系统、不执行任何作业。",
        "dir_label": "SQL 目录",
        "dir_ph": "包含 *.sql 的目录（递归扫描），如 examples/dagcheck_demo",
        "st_label": "SeaTunnel 配置目录（可选）",
        "st_ph": "合并 *.conf 的 source→sink 血缘",
        "dialect_label": "SQL 方言",
        "check_btn": "体检 DAG",
        "empty_dir": "⚠️ 请先填写 SQL 目录。",
        "bad_dir": "⚠️ 不是有效目录: ",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_dag_check_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-dag-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-dag-side"]):
                dir_box = gr.Textbox(
                    label=t("dir_label"), placeholder=t("dir_ph"),
                    value="examples/dagcheck_demo")
                st_box = gr.Textbox(
                    label=t("st_label"), placeholder=t("st_ph"))
                dialect_dd = gr.Dropdown(
                    choices=_DIALECTS, value="hive",
                    label=t("dialect_label"))
                check_btn = gr.Button(t("check_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-dag-main"]):
                report_md = gr.Markdown("")

    # ── callbacks ──

    def do_check(dir_text: str, st_text: str, dialect: str, lang: str):
        from pathlib import Path
        lang = normalize_lang(lang)
        if not (dir_text or "").strip():
            return _t(lang, "empty_dir")
        if not Path(dir_text.strip()).is_dir():
            return _t(lang, "bad_dir") + dir_text
        st_dir = (st_text or "").strip() or None
        if st_dir and not Path(st_dir).is_dir():
            return _t(lang, "bad_dir") + st_dir
        try:
            report = check_sql_dir(dir_text.strip(), dialect=dialect,
                                   seatunnel_dir=st_dir)
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
            gr.update(label=_t(lang, "st_label"),
                      placeholder=_t(lang, "st_ph")),
            gr.update(label=_t(lang, "dialect_label")),
            gr.update(value=_t(lang, "check_btn")),
        )

    check_btn.click(
        do_check,
        inputs=[dir_box, st_box, dialect_dd, lang_state],
        outputs=[report_md],
    )

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, dir_box, st_box, dialect_dd,
                 check_btn],
    )
