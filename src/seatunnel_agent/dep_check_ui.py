# -*- coding: utf-8 -*-
"""Gradio page for dependency health.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Dependency Health", "/depcheck")``.  Offline: declared vs
installed, pins and licenses.
"""

from __future__ import annotations

import gradio as gr

from .dep_check import (
    check,
    collect_from_path,
    parse_pyproject_text,
    parse_requirements_text,
    render_markdown,
)
from .dep_check.report import normalize_lang

_I18N = {
    "en": {
        "title": "## 📦 Dependency Health\n"
                 "Declared vs installed, unpinned specs, conflicting pins "
                 "and a license inventory (copyleft flagged) — fully "
                 "offline. CI gate: `seatunnel-agent depcheck --fail-on "
                 "high`.",
        "text_label": "pyproject.toml or requirements.txt content",
        "text_ph": "Paste a pyproject.toml ([project] deps) or "
                   "requirements.txt…",
        "check_btn": "Check pasted text",
        "self_btn": "Check this project",
        "report_ph": "▶ Findings and the dependency inventory appear here.",
        "empty_text": "⚠️ Paste some metadata first.",
    },
    "zh": {
        "title": "## 📦 依赖体检\n"
                 "声明 vs 实装、未钉版本、重复/冲突声明与 License 清单"
                 "(copyleft 标记)— 全离线。CI 门禁:"
                 "`seatunnel-agent depcheck --fail-on high`。",
        "text_label": "pyproject.toml 或 requirements.txt 内容",
        "text_ph": "粘贴 pyproject.toml([project] 依赖)或 "
                   "requirements.txt…",
        "check_btn": "检查粘贴内容",
        "self_btn": "检查本项目",
        "report_ph": "▶ 检查后在此显示问题与依赖清单。",
        "empty_text": "⚠️ 请先粘贴依赖声明。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_dep_check_page(app: gr.Blocks) -> None:
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
                text_box = gr.Textbox(label=t("text_label"),
                                      placeholder=t("text_ph"), lines=12)
                check_btn = gr.Button(t("check_btn"), variant="primary")
                self_btn = gr.Button(t("self_btn"), size="sm")

            with gr.Column(scale=5, elem_classes=["st-fmt-main"]):
                report_md = gr.Markdown(t("report_ph"))

    # ── callbacks ──

    def do_check_text(text: str, lang: str):
        lang = normalize_lang(lang)
        if not (text or "").strip():
            return _t(lang, "empty_text")
        try:
            if "[project]" in text or "[build-system]" in text:
                reqs = parse_pyproject_text(text)
            else:
                reqs = parse_requirements_text(text)
            return render_markdown(check(reqs), lang)
        except Exception as exc:  # noqa: BLE001 — never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"

    def do_check_self(lang: str):
        lang = normalize_lang(lang)
        try:
            return render_markdown(check(collect_from_path(".")), lang)
        except Exception as exc:  # noqa: BLE001
            return f"⚠️ {type(exc).__name__}: {exc}"

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "text_label"),
                      placeholder=_t(lang, "text_ph")),
            gr.update(value=_t(lang, "check_btn")),
            gr.update(value=_t(lang, "self_btn")),
        )

    check_btn.click(do_check_text, inputs=[text_box, lang_state],
                    outputs=[report_md])
    self_btn.click(do_check_self, inputs=[lang_state], outputs=[report_md])

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(current_report: str, request: gr.Request):
        lang_tuple = switch_lang(choice_from_request(request))
        placeholders = {_t("zh", "report_ph"), _t("en", "report_ph"), ""}
        rep_upd = (gr.update(value=_t(lang_tuple[0], "report_ph"))
                   if (current_report or "").strip() in placeholders
                   else gr.update())
        return (*lang_tuple, rep_upd)

    app.load(
        _lang_on_load, inputs=[report_md],
        outputs=[lang_state, title_md, text_box, check_btn, self_btn,
                 report_md],
    )
