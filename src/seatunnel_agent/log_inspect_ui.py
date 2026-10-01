# -*- coding: utf-8 -*-
"""Gradio page for the batch log inspection agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Log Inspect", "/loginspect")``.  The deterministic clustering
runs fully in-process; LLM root-cause advice is an optional, clearly-marked
add-on that never overwrites the deterministic result.
"""

from __future__ import annotations

import gradio as gr

from .log_inspect import render_markdown, scan_dir, scan_text
from .log_inspect.i18n import normalize_lang

_I18N = {
    "en": {
        "title": "## 🧾 Batch Log Inspection\n"
                 "Exception clustering over a log directory — ERROR/WARN "
                 "events are normalized and grouped by root cause, so a "
                 "noisy directory collapses into Top-N distinct problems. "
                 "Deterministic, nothing executed.",
        "dir_label": "Log directory",
        "dir_ph": "Directory containing *.log files (scanned recursively), "
                  "e.g. examples/logs_demo",
        "warn_label": "Include WARN events",
        "top_label": "Top clusters",
        "scan_btn": "Inspect directory",
        "inline_acc": "Inspect pasted log text",
        "text_label": "Log text",
        "text_ph": "Paste log lines / a stack trace…",
        "scan_text_btn": "Inspect text",
        "empty_dir": "⚠️ Provide a log directory first.",
        "bad_dir": "⚠️ Not a directory: ",
        "empty_text": "⚠️ Paste some log text first.",
        "advice_acc": "LLM advice (optional, llm-generated)",
        "advice_btn": "Generate LLM advice",
        "advice_none": "*No clusters to advise on — run a scan first.*",
        "advice_no_key": "*No API key configured — deterministic results "
                         "above are unaffected.*",
    },
    "zh": {
        "title": "## 🧾 批量日志巡检\n"
                 "对日志目录做异常聚类 — ERROR/WARN 事件按根因归一化分组，"
                 "嘈杂的日志目录收敛成 Top-N 个不同的问题。确定性扫描，"
                 "不执行任何操作。",
        "dir_label": "日志目录",
        "dir_ph": "包含 *.log 的目录（递归扫描），如 examples/logs_demo",
        "warn_label": "包含 WARN 事件",
        "top_label": "Top 簇数",
        "scan_btn": "巡检目录",
        "inline_acc": "巡检粘贴的日志",
        "text_label": "日志文本",
        "text_ph": "粘贴日志行 / 异常堆栈…",
        "scan_text_btn": "巡检文本",
        "empty_dir": "⚠️ 请先填写日志目录。",
        "bad_dir": "⚠️ 不是有效目录: ",
        "empty_text": "⚠️ 请先粘贴日志文本。",
        "advice_acc": "LLM 建议（可选，llm-generated）",
        "advice_btn": "生成 LLM 建议",
        "advice_none": "*没有可分析的异常簇 — 请先执行巡检。*",
        "advice_no_key": "*未配置 API key — 上方确定性结果不受影响。*",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_log_inspect_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)
    report_state = gr.State(None)   # InspectReport | None (for LLM advice)

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-lgi-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-lgi-side"]):
                dir_box = gr.Textbox(
                    label=t("dir_label"), placeholder=t("dir_ph"),
                    value="examples/logs_demo")
                warn_cb = gr.Checkbox(value=True, label=t("warn_label"))
                top_slider = gr.Slider(
                    minimum=3, maximum=50, value=10, step=1,
                    label=t("top_label"))
                scan_btn = gr.Button(t("scan_btn"), variant="primary")
                with gr.Accordion(t("inline_acc"), open=False) as inline_acc:
                    text_box = gr.Textbox(
                        label=t("text_label"), placeholder=t("text_ph"),
                        lines=8)
                    scan_text_btn = gr.Button(t("scan_text_btn"))

            with gr.Column(scale=5, elem_classes=["st-lgi-main"]):
                report_md = gr.Markdown("")
                with gr.Accordion(t("advice_acc"), open=False) as advice_acc:
                    advice_btn = gr.Button(t("advice_btn"), size="sm")
                    advice_md = gr.Markdown("")

    # ── callbacks ──

    def do_scan_dir(dir_text: str, include_warn: bool, top: float,
                    lang: str):
        from pathlib import Path
        lang = normalize_lang(lang)
        if not (dir_text or "").strip():
            return _t(lang, "empty_dir"), None, ""
        if not Path(dir_text.strip()).is_dir():
            return _t(lang, "bad_dir") + dir_text, None, ""
        try:
            report = scan_dir(dir_text.strip(), include_warn=include_warn)
        except Exception as exc:  # noqa: BLE001 — scan must never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}", None, ""
        return render_markdown(report, lang, top=int(top)), report, ""

    def do_scan_text(text: str, include_warn: bool, top: float, lang: str):
        lang = normalize_lang(lang)
        if not (text or "").strip():
            return _t(lang, "empty_text"), None, ""
        report = scan_text(text, include_warn=include_warn)
        return render_markdown(report, lang, top=int(top)), report, ""

    def do_advice(report, lang: str):
        lang = normalize_lang(lang)
        if report is None or not report.clusters:
            return _t(lang, "advice_none")
        try:
            from .config import load_settings
            settings = load_settings()
        except RuntimeError:
            return _t(lang, "advice_no_key")
        try:
            from .log_inspect.advisor import generate_advice
            return generate_advice(settings, report, lang) \
                or _t(lang, "advice_none")
        except Exception as exc:  # noqa: BLE001 — advice must never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "dir_label"),
                      placeholder=_t(lang, "dir_ph")),
            gr.update(label=_t(lang, "warn_label")),
            gr.update(label=_t(lang, "top_label")),
            gr.update(value=_t(lang, "scan_btn")),
            gr.update(label=_t(lang, "inline_acc")),
            gr.update(label=_t(lang, "text_label"),
                      placeholder=_t(lang, "text_ph")),
            gr.update(value=_t(lang, "scan_text_btn")),
            gr.update(label=_t(lang, "advice_acc")),
            gr.update(value=_t(lang, "advice_btn")),
        )

    scan_btn.click(
        do_scan_dir,
        inputs=[dir_box, warn_cb, top_slider, lang_state],
        outputs=[report_md, report_state, advice_md],
    )
    scan_text_btn.click(
        do_scan_text,
        inputs=[text_box, warn_cb, top_slider, lang_state],
        outputs=[report_md, report_state, advice_md],
    )
    advice_btn.click(
        do_advice,
        inputs=[report_state, lang_state],
        outputs=[advice_md],
    )

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, dir_box, warn_cb, top_slider,
                 scan_btn, inline_acc, text_box, scan_text_btn,
                 advice_acc, advice_btn],
    )
