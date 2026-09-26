# -*- coding: utf-8 -*-
"""Gradio page for the SQL dialect translation agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("SQL Transpile", "/transpile")``.  The deterministic path runs
fully in-process (sqlglot); LLM advice is an optional, clearly-marked
add-on that never overwrites the deterministic result.
"""

from __future__ import annotations

import gradio as gr

from .sql_transpile import (
    DIALECTS,
    render_batch_markdown,
    render_markdown,
    translate,
    transpile_dir,
)
from .sql_transpile.i18n import normalize_lang

_I18N = {
    "en": {
        "title": "## 🔁 SQL Dialect Translation\n"
                 "hive / spark / doris / starrocks — deterministic sqlglot "
                 "translation with a structured incompatibility report. "
                 "No database connection, the SQL is never executed.",
        "src_label": "Source dialect",
        "src_auto": "Auto detect",
        "dst_label": "Target dialect",
        "sql_label": "SQL input",
        "sql_ph": "Paste one or more ;-separated statements…",
        "translate_btn": "Translate",
        "batch_acc": "Batch translate a directory",
        "dir_label": "SQL directory",
        "dir_ph": "Directory containing *.sql files (scanned recursively)",
        "out_label": "Output directory (optional)",
        "out_ph": "Translated files mirror the input tree when set",
        "batch_btn": "Batch translate",
        "result_label": "Translated SQL",
        "empty_sql": "⚠️ Paste some SQL first.",
        "empty_dir": "⚠️ Provide a SQL directory first.",
        "bad_dir": "⚠️ Not a directory: ",
        "advice_acc": "LLM advice (optional, llm-generated)",
        "advice_btn": "Generate LLM advice",
        "advice_none": "*No findings that need LLM advice.*",
        "advice_no_key": "*No API key configured — deterministic results above are unaffected.*",
    },
    "zh": {
        "title": "## 🔁 SQL 方言翻译\n"
                 "hive / spark / doris / starrocks 互转 — 基于 sqlglot 的确定性"
                 "翻译 + 结构化不兼容点清单。不连接数据库，不执行 SQL。",
        "src_label": "源方言",
        "src_auto": "自动推断",
        "dst_label": "目标方言",
        "sql_label": "SQL 输入",
        "sql_ph": "粘贴一条或多条以 ; 分隔的 SQL…",
        "translate_btn": "翻译",
        "batch_acc": "批量翻译目录",
        "dir_label": "SQL 目录",
        "dir_ph": "包含 *.sql 的目录（递归扫描）",
        "out_label": "输出目录（可选）",
        "out_ph": "填写后按原目录结构写出翻译文件",
        "batch_btn": "批量翻译",
        "result_label": "翻译后 SQL",
        "empty_sql": "⚠️ 请先粘贴 SQL。",
        "empty_dir": "⚠️ 请先填写 SQL 目录。",
        "bad_dir": "⚠️ 不是有效目录: ",
        "advice_acc": "LLM 建议（可选，llm-generated）",
        "advice_btn": "生成 LLM 建议",
        "advice_none": "*没有需要 LLM 建议的不兼容点。*",
        "advice_no_key": "*未配置 API key — 上方确定性结果不受影响。*",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def _src_choices(lang: str) -> list[tuple[str, str]]:
    return [(_t(lang, "src_auto"), "auto")] + [(d, d) for d in DIALECTS]


def render_sql_transpile_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)
    result_state = gr.State(None)  # TranspileResult | None (for LLM advice)

    with gr.Column(elem_classes=["st-trp-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-trp-side"]):
                src_dd = gr.Dropdown(
                    choices=_src_choices(lang0), value="auto",
                    label=t("src_label"))
                dst_dd = gr.Dropdown(
                    choices=list(DIALECTS), value="doris",
                    label=t("dst_label"))
                sql_box = gr.Textbox(
                    label=t("sql_label"), placeholder=t("sql_ph"), lines=10,
                    elem_id="trp-sql-box")
                translate_btn = gr.Button(t("translate_btn"), variant="primary")
                with gr.Accordion(t("batch_acc"), open=False) as batch_acc:
                    dir_box = gr.Textbox(
                        label=t("dir_label"), placeholder=t("dir_ph"))
                    out_box = gr.Textbox(
                        label=t("out_label"), placeholder=t("out_ph"))
                    batch_btn = gr.Button(t("batch_btn"))

            with gr.Column(scale=5, elem_classes=["st-trp-main"]):
                out_code = gr.Code(
                    language="sql", label=t("result_label"), value="")
                report_md = gr.Markdown("")
                with gr.Accordion(t("advice_acc"), open=False) as advice_acc:
                    advice_btn = gr.Button(t("advice_btn"), size="sm")
                    advice_md = gr.Markdown("")

    # ── callbacks ──

    def do_translate(sql_text: str, src: str, dst: str, lang: str):
        lang = normalize_lang(lang)
        if not (sql_text or "").strip():
            return "", _t(lang, "empty_sql"), None, ""
        try:
            result = translate(
                sql_text, dst=dst, src=None if src == "auto" else src)
        except ValueError as exc:
            return "", f"⚠️ {exc}", None, ""
        script = result.output_script() if any(
            s.ok for s in result.statements) else ""
        return script, render_markdown(result, lang), result, ""

    def do_batch(dir_text: str, out_text: str, src: str, dst: str,
                 lang: str):
        from pathlib import Path
        lang = normalize_lang(lang)
        if not (dir_text or "").strip():
            return "", _t(lang, "empty_dir"), None, ""
        if not Path(dir_text.strip()).is_dir():
            return "", _t(lang, "bad_dir") + dir_text, None, ""
        try:
            batch = transpile_dir(
                dir_text.strip(), dst=dst,
                src=None if src == "auto" else src,
                out_dir=(out_text or "").strip() or None)
        except ValueError as exc:
            return "", f"⚠️ {exc}", None, ""
        return "", render_batch_markdown(batch, lang), None, ""

    def do_advice(result, lang: str):
        lang = normalize_lang(lang)
        if result is None:
            return _t(lang, "advice_none")
        from .sql_transpile.advisor import advisable_issues, generate_advice
        if not advisable_issues(result):
            return _t(lang, "advice_none")
        try:
            from .config import load_settings
            settings = load_settings()
        except RuntimeError:
            return _t(lang, "advice_no_key")
        try:
            return generate_advice(settings, result, lang) \
                or _t(lang, "advice_none")
        except Exception as exc:  # noqa: BLE001 — advice must never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "src_label"),
                      choices=_src_choices(lang)),
            gr.update(label=_t(lang, "dst_label")),
            gr.update(label=_t(lang, "sql_label"),
                      placeholder=_t(lang, "sql_ph")),
            gr.update(value=_t(lang, "translate_btn")),
            gr.update(label=_t(lang, "batch_acc")),
            gr.update(label=_t(lang, "dir_label"),
                      placeholder=_t(lang, "dir_ph")),
            gr.update(label=_t(lang, "out_label"),
                      placeholder=_t(lang, "out_ph")),
            gr.update(value=_t(lang, "batch_btn")),
            gr.update(label=_t(lang, "result_label")),
            gr.update(label=_t(lang, "advice_acc")),
            gr.update(value=_t(lang, "advice_btn")),
        )

    translate_btn.click(
        do_translate,
        inputs=[sql_box, src_dd, dst_dd, lang_state],
        outputs=[out_code, report_md, result_state, advice_md],
    )
    batch_btn.click(
        do_batch,
        inputs=[dir_box, out_box, src_dd, dst_dd, lang_state],
        outputs=[out_code, report_md, result_state, advice_md],
    )
    advice_btn.click(
        do_advice,
        inputs=[result_state, lang_state],
        outputs=[advice_md],
    )
    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    # Language follows the hub's choice (st-lang cookie), applied on load.
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, src_dd, dst_dd, sql_box,
                 translate_btn, batch_acc, dir_box, out_box, batch_btn,
                 out_code, advice_acc, advice_btn],
    )
    # SQL handed over from the review page (localStorage bridge): fill the
    # box and fire an input event so gradio picks the value up.
    app.load(fn=None, js="""
        () => setTimeout(() => {
            const v = localStorage.getItem('st_transpile_sql');
            if (!v) return;
            const t = document.querySelector('#trp-sql-box textarea');
            if (t) {
                // remove only after successful delivery: if the textarea
                // is not hydrated yet, the payload survives for a reload
                localStorage.removeItem('st_transpile_sql');
                t.value = v;
                t.dispatchEvent(new Event('input', {bubbles: true}));
            }
        }, 600)""")
