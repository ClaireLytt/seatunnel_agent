# -*- coding: utf-8 -*-
"""Gradio page for the change impact analysis agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Change Impact", "/impact")``.  Fully deterministic: two SQL
trees in, blast-radius report out — no database, no LLM.
"""

from __future__ import annotations

import gradio as gr

from .data_lineage.sqlglot_lineage import SQL_DIALECTS

_I18N = {
    "en": {
        "title": "## 💥 Change Impact Analysis\n"
                 "SQL diff × lineage: compare two SQL trees and report the "
                 "release blast radius — changed tables, downstream impact "
                 "and severity (error / warn / info). No database "
                 "connection, the SQL is never executed.",
        "old_label": "Old SQL directory",
        "old_ph": "SQL tree before the change, e.g. examples/impact_demo/old",
        "new_label": "New SQL directory",
        "new_ph": "SQL tree after the change, e.g. examples/impact_demo/new",
        "dialect_label": "SQL dialect",
        "depth_label": "Downstream depth",
        "analyze_btn": "Analyze change impact",
        "result_ph": "*Fill both directories and click Analyze.*",
        "need_dirs": "⚠️ Provide both the old and the new SQL directory.",
        "bad_dir": "❌ Not a directory: `{d}`",
        "fail": "❌ **Analysis failed**: {exc}",
    },
    "zh": {
        "title": "## 💥 变更影响分析\n"
                 "SQL 变更 × 血缘：对比两份 SQL 目录，输出上线影响面——"
                 "变更了哪些表、下游波及多深、按严重度分级"
                 "（error / warn / info）。不连接数据库，不执行 SQL。",
        "old_label": "旧 SQL 目录",
        "old_ph": "变更前的 SQL 目录，如 examples/impact_demo/old",
        "new_label": "新 SQL 目录",
        "new_ph": "变更后的 SQL 目录，如 examples/impact_demo/new",
        "dialect_label": "SQL 方言",
        "depth_label": "下游深度",
        "analyze_btn": "变更影响分析",
        "result_ph": "*填写新旧两个目录后点击分析。*",
        "need_dirs": "⚠️ 请同时填写旧、新两个 SQL 目录。",
        "bad_dir": "❌ 不是有效目录: `{d}`",
        "fail": "❌ **分析失败**: {exc}",
    },
}


def _t(lang: str, key: str) -> str:
    lang = "en" if (lang or "").lower().startswith("en") else "zh"
    return _I18N[lang].get(key, key)


def render_impact_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    with gr.Column(elem_classes=["st-imp-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            lang_dd = gr.Dropdown(
                choices=["English", "中文"], value="English",
                show_label=False, container=False, min_width=140, scale=0,
                elem_classes=["st-lang-dd"],
            )

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-imp-side"]):
                old_box = gr.Textbox(
                    label=t("old_label"), placeholder=t("old_ph"))
                new_box = gr.Textbox(
                    label=t("new_label"), placeholder=t("new_ph"))
                dialect_dd = gr.Dropdown(
                    choices=list(SQL_DIALECTS), value="hive",
                    label=t("dialect_label"))
                depth_sl = gr.Slider(1, 10, value=3, step=1,
                                     label=t("depth_label"))
                analyze_btn = gr.Button(t("analyze_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-imp-main"]):
                report_md = gr.Markdown(t("result_ph"))

    # ── callbacks ──

    def do_analyze(old_dir: str, new_dir: str, dialect: str, depth: float,
                   lang: str):
        from pathlib import Path

        from .data_lineage.impact import analyze_dirs, render_impact_markdown

        old_dir = (old_dir or "").strip()
        new_dir = (new_dir or "").strip()
        if not old_dir or not new_dir:
            return _t(lang, "need_dirs")
        for d in (old_dir, new_dir):
            if not Path(d).is_dir():
                return _t(lang, "bad_dir").format(d=d)
        try:
            result = analyze_dirs(old_dir, new_dir, depth=int(depth),
                                  sql_dialect=dialect or "hive")
        except Exception as exc:  # noqa: BLE001 — surface any failure in the UI
            return _t(lang, "fail").format(exc=exc)
        return render_impact_markdown(result, lang)

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "old_label"),
                      placeholder=_t(lang, "old_ph")),
            gr.update(label=_t(lang, "new_label"),
                      placeholder=_t(lang, "new_ph")),
            gr.update(label=_t(lang, "dialect_label")),
            gr.update(label=_t(lang, "depth_label")),
            gr.update(value=_t(lang, "analyze_btn")),
        )

    analyze_btn.click(
        do_analyze,
        inputs=[old_box, new_box, dialect_dd, depth_sl, lang_state],
        outputs=[report_md],
    )
    lang_dd.change(
        switch_lang,
        inputs=[lang_dd],
        outputs=[lang_state, title_md, old_box, new_box, dialect_dd,
                 depth_sl, analyze_btn],
    )
