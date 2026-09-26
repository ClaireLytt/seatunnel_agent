# -*- coding: utf-8 -*-
"""Gradio page for the change impact analysis agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Change Impact", "/impact")``.  Fully deterministic: two SQL
trees (or two pasted snippets) in, blast-radius report out — no database,
no LLM.
"""

from __future__ import annotations

import gradio as gr

from .data_lineage.sqlglot_lineage import SQL_DIALECTS

# Tab headers stay bilingual and static: gradio tab labels are not reliably
# updatable at runtime, and the UI-test cases click them by visible text.
_TAB_DIRS = "目录模式 Directories"
_TAB_PASTE = "粘贴 SQL Paste SQL"

_I18N = {
    "en": {
        "title": "## 💥 Change Impact Analysis\n"
                 "SQL diff × lineage: compare two SQL trees — or just paste "
                 "the before/after SQL — and report the release blast "
                 "radius: changed tables, downstream impact and severity "
                 "(error / warn / info). No database connection, the SQL is "
                 "never executed.",
        "old_label": "Old SQL directory",
        "old_ph": "SQL tree before the change, e.g. examples/impact_demo/old",
        "new_label": "New SQL directory",
        "new_ph": "SQL tree after the change, e.g. examples/impact_demo/new",
        "old_sql_label": "Old SQL",
        "old_sql_ph": "Paste the SQL before the change…",
        "new_sql_label": "New SQL",
        "new_sql_ph": "Paste the SQL after the change…",
        "ctx_label": "Context SQL directory (optional)",
        "ctx_ph": "Repo SQL tree; widens the blast radius to real consumers",
        "dialect_label": "SQL dialect",
        "depth_label": "Downstream depth",
        "analyze_btn": "Analyze change impact",
        "analyze_sql_btn": "Analyze pasted SQL",
        "result_ph": "*Fill both sides and click Analyze.*",
        "need_dirs": "⚠️ Provide both the old and the new SQL directory.",
        "need_sql": "⚠️ Paste both the old and the new SQL.",
        "bad_dir": "❌ Not a directory: `{d}`",
        "fail": "❌ **Analysis failed**: {exc}",
    },
    "zh": {
        "title": "## 💥 变更影响分析\n"
                 "SQL 变更 × 血缘：对比两份 SQL 目录，或直接粘贴改动前后的"
                 "两段 SQL，输出上线影响面——变更了哪些表、下游波及多深、"
                 "按严重度分级（error / warn / info）。不连接数据库，"
                 "不执行 SQL。",
        "old_label": "旧 SQL 目录",
        "old_ph": "变更前的 SQL 目录，如 examples/impact_demo/old",
        "new_label": "新 SQL 目录",
        "new_ph": "变更后的 SQL 目录，如 examples/impact_demo/new",
        "old_sql_label": "旧 SQL",
        "old_sql_ph": "粘贴变更前的 SQL…",
        "new_sql_label": "新 SQL",
        "new_sql_ph": "粘贴变更后的 SQL…",
        "ctx_label": "上下文 SQL 目录（可选）",
        "ctx_ph": "仓库 SQL 目录；填写后下游波及按全仓血缘计算",
        "dialect_label": "SQL 方言",
        "depth_label": "下游深度",
        "analyze_btn": "变更影响分析",
        "analyze_sql_btn": "分析粘贴的 SQL",
        "result_ph": "*填写两侧内容后点击分析。*",
        "need_dirs": "⚠️ 请同时填写旧、新两个 SQL 目录。",
        "need_sql": "⚠️ 请同时粘贴旧、新两段 SQL。",
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
                with gr.Tabs():
                    with gr.Tab(_TAB_DIRS):
                        old_box = gr.Textbox(
                            label=t("old_label"), placeholder=t("old_ph"))
                        new_box = gr.Textbox(
                            label=t("new_label"), placeholder=t("new_ph"))
                        analyze_btn = gr.Button(
                            t("analyze_btn"), variant="primary")
                    with gr.Tab(_TAB_PASTE):
                        old_sql_box = gr.Textbox(
                            label=t("old_sql_label"),
                            placeholder=t("old_sql_ph"), lines=8)
                        new_sql_box = gr.Textbox(
                            label=t("new_sql_label"),
                            placeholder=t("new_sql_ph"), lines=8)
                        ctx_box = gr.Textbox(
                            label=t("ctx_label"), placeholder=t("ctx_ph"))
                        analyze_sql_btn = gr.Button(
                            t("analyze_sql_btn"), variant="primary")
                dialect_dd = gr.Dropdown(
                    choices=list(SQL_DIALECTS), value="hive",
                    label=t("dialect_label"))
                depth_sl = gr.Slider(1, 10, value=3, step=1,
                                     label=t("depth_label"))

            with gr.Column(scale=5, elem_classes=["st-imp-main"]):
                graph_html = gr.HTML("")
                report_md = gr.Markdown(t("result_ph"))

    # ── callbacks ──

    def _graph_iframe(result) -> str:
        import html as _html

        from .data_lineage.impact import render_impact_mermaid
        from .data_lineage.render import mermaid_html

        src = render_impact_mermaid(result)
        if not src:
            return ""
        # full html.escape (same as lineage_ui): the browser entity-decodes
        # the srcdoc attribute once, so escaping only '"' would let &lt;/&amp;
        # from table names decode back into live markup inside the
        # same-origin iframe.
        return ('<iframe style="width:100%;height:340px;border:1px solid '
                '#e5e7eb;border-radius:8px" srcdoc="'
                + _html.escape(mermaid_html(src)) + '"></iframe>')

    def do_analyze(old_dir: str, new_dir: str, dialect: str, depth: float,
                   lang: str):
        from pathlib import Path

        from .data_lineage.impact import analyze_dirs, render_impact_markdown

        old_dir = (old_dir or "").strip()
        new_dir = (new_dir or "").strip()
        if not old_dir or not new_dir:
            return "", _t(lang, "need_dirs")
        for d in (old_dir, new_dir):
            if not Path(d).is_dir():
                return "", _t(lang, "bad_dir").format(d=d)
        try:
            result = analyze_dirs(old_dir, new_dir, depth=int(depth),
                                  sql_dialect=dialect or "hive")
        except Exception as exc:  # noqa: BLE001 — surface any failure in the UI
            return "", _t(lang, "fail").format(exc=exc)
        return _graph_iframe(result), render_impact_markdown(result, lang)

    def do_analyze_sql(old_sql: str, new_sql: str, ctx_dir: str,
                       dialect: str, depth: float, lang: str):
        from pathlib import Path

        from .data_lineage.impact import (
            analyze_sql_texts, render_impact_markdown, render_text_diff,
        )

        if not (old_sql or "").strip() or not (new_sql or "").strip():
            return "", _t(lang, "need_sql")
        ctx_dir = (ctx_dir or "").strip() or None
        if ctx_dir and not Path(ctx_dir).is_dir():
            return "", _t(lang, "bad_dir").format(d=ctx_dir)
        try:
            result = analyze_sql_texts(old_sql, new_sql, depth=int(depth),
                                       sql_dialect=dialect or "hive",
                                       context_dir=ctx_dir)
        except Exception as exc:  # noqa: BLE001 — surface any failure in the UI
            return "", _t(lang, "fail").format(exc=exc)
        report = render_impact_markdown(result, lang)
        text_diff = render_text_diff(old_sql, new_sql)
        if text_diff:
            report = f"{report}\n\n{text_diff}"
        return _graph_iframe(result), report

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "old_label"),
                      placeholder=_t(lang, "old_ph")),
            gr.update(label=_t(lang, "new_label"),
                      placeholder=_t(lang, "new_ph")),
            gr.update(label=_t(lang, "old_sql_label"),
                      placeholder=_t(lang, "old_sql_ph")),
            gr.update(label=_t(lang, "new_sql_label"),
                      placeholder=_t(lang, "new_sql_ph")),
            gr.update(label=_t(lang, "ctx_label"),
                      placeholder=_t(lang, "ctx_ph")),
            gr.update(label=_t(lang, "dialect_label")),
            gr.update(label=_t(lang, "depth_label")),
            gr.update(value=_t(lang, "analyze_btn")),
            gr.update(value=_t(lang, "analyze_sql_btn")),
        )

    analyze_btn.click(
        do_analyze,
        inputs=[old_box, new_box, dialect_dd, depth_sl, lang_state],
        outputs=[graph_html, report_md],
    )
    analyze_sql_btn.click(
        do_analyze_sql,
        inputs=[old_sql_box, new_sql_box, ctx_box, dialect_dd, depth_sl,
                lang_state],
        outputs=[graph_html, report_md],
    )
    lang_dd.change(
        switch_lang,
        inputs=[lang_dd],
        outputs=[lang_state, title_md, old_box, new_box, old_sql_box,
                 new_sql_box, ctx_box, dialect_dd, depth_sl, analyze_btn,
                 analyze_sql_btn],
    )
