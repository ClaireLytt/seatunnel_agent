# -*- coding: utf-8 -*-
"""Gradio page for the schema drift agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Schema Drift", "/schemadrift")``.  Fully deterministic —
no database, no LLM, nothing executed; diffs CREATE TABLE scripts only.
"""

from __future__ import annotations

import gradio as gr

from .schema_drift import diff_paths, diff_scripts, render_markdown
from .schema_drift.i18n import normalize_lang

_DIALECTS = ["hive", "spark", "mysql", "postgresql", "clickhouse",
             "doris", "starrocks"]

_I18N = {
    "en": {
        "title": "## 🧬 Schema Drift Check\n"
                 "Compare two schema snapshots (CREATE TABLE scripts) and "
                 "report every structural change with a severity level — "
                 "breaking / risk / info. Sibling of /impact: that page "
                 "covers SQL logic changes, this one covers table "
                 "structure. No database connection.",
        "dialect_label": "SQL dialect",
        "old_label": "Old DDL",
        "old_ph": "Paste the old CREATE TABLE script…",
        "new_label": "New DDL",
        "new_ph": "Paste the new CREATE TABLE script…",
        "diff_btn": "Compare",
        "dirs_acc": "Compare two directories",
        "old_dir_label": "Old directory / file",
        "new_dir_label": "New directory / file",
        "dirs_btn": "Compare directories",
        "empty_sql": "⚠️ Paste both DDL scripts first.",
        "empty_dirs": "⚠️ Provide both paths first.",
        "bad_path": "⚠️ Path does not exist: ",
    },
    "zh": {
        "title": "## 🧬 Schema 漂移检查\n"
                 "对比两份 Schema 快照（CREATE TABLE 脚本），按严重度分级"
                 "报告每一处结构变更 — 破坏 / 风险 / 提示。与变更影响分析"
                 "(/impact) 互补：那里管 SQL 逻辑变更，这里管表结构变更。"
                 "不连接数据库。",
        "dialect_label": "SQL 方言",
        "old_label": "旧版 DDL",
        "old_ph": "粘贴旧版 CREATE TABLE 脚本…",
        "new_label": "新版 DDL",
        "new_ph": "粘贴新版 CREATE TABLE 脚本…",
        "diff_btn": "对比",
        "dirs_acc": "对比两个目录",
        "old_dir_label": "旧目录 / 文件",
        "new_dir_label": "新目录 / 文件",
        "dirs_btn": "对比目录",
        "empty_sql": "⚠️ 请先粘贴两份 DDL。",
        "empty_dirs": "⚠️ 请先填写两个路径。",
        "bad_path": "⚠️ 路径不存在: ",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_schema_drift_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-sdf-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-sdf-side"]):
                dialect_dd = gr.Dropdown(
                    choices=_DIALECTS, value="hive",
                    label=t("dialect_label"))
                old_box = gr.Textbox(
                    label=t("old_label"), placeholder=t("old_ph"), lines=8)
                new_box = gr.Textbox(
                    label=t("new_label"), placeholder=t("new_ph"), lines=8)
                diff_btn = gr.Button(t("diff_btn"), variant="primary")
                with gr.Accordion(t("dirs_acc"), open=False) as dirs_acc:
                    old_dir_box = gr.Textbox(
                        label=t("old_dir_label"),
                        value="examples/schema_drift_demo/old")
                    new_dir_box = gr.Textbox(
                        label=t("new_dir_label"),
                        value="examples/schema_drift_demo/new")
                    dirs_btn = gr.Button(t("dirs_btn"))

            with gr.Column(scale=5, elem_classes=["st-sdf-main"]):
                report_md = gr.Markdown("")

    # ── callbacks ──

    def do_diff(old_sql: str, new_sql: str, dialect: str, lang: str):
        lang = normalize_lang(lang)
        if not (old_sql or "").strip() or not (new_sql or "").strip():
            return _t(lang, "empty_sql")
        try:
            report = diff_scripts(old_sql, new_sql, dialect=dialect)
        except Exception as exc:  # noqa: BLE001 — diff must never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"
        return render_markdown(report, lang)

    def do_diff_dirs(old_dir: str, new_dir: str, dialect: str, lang: str):
        from pathlib import Path
        lang = normalize_lang(lang)
        if not (old_dir or "").strip() or not (new_dir or "").strip():
            return _t(lang, "empty_dirs")
        for raw in (old_dir.strip(), new_dir.strip()):
            if not Path(raw).exists():
                return _t(lang, "bad_path") + raw
        try:
            report = diff_paths(old_dir.strip(), new_dir.strip(),
                                dialect=dialect)
        except Exception as exc:  # noqa: BLE001
            return f"⚠️ {type(exc).__name__}: {exc}"
        return render_markdown(report, lang)

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "dialect_label")),
            gr.update(label=_t(lang, "old_label"),
                      placeholder=_t(lang, "old_ph")),
            gr.update(label=_t(lang, "new_label"),
                      placeholder=_t(lang, "new_ph")),
            gr.update(value=_t(lang, "diff_btn")),
            gr.update(label=_t(lang, "dirs_acc")),
            gr.update(label=_t(lang, "old_dir_label")),
            gr.update(label=_t(lang, "new_dir_label")),
            gr.update(value=_t(lang, "dirs_btn")),
        )

    diff_btn.click(
        do_diff,
        inputs=[old_box, new_box, dialect_dd, lang_state],
        outputs=[report_md],
    )
    dirs_btn.click(
        do_diff_dirs,
        inputs=[old_dir_box, new_dir_box, dialect_dd, lang_state],
        outputs=[report_md],
    )

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, dialect_dd, old_box, new_box,
                 diff_btn, dirs_acc, old_dir_box, new_dir_box, dirs_btn],
    )
