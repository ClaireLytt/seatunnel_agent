# -*- coding: utf-8 -*-
"""Gradio page for the release-notes helper.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Release Notes", "/release")``.  Paste a commit log (or pull it
from this repo), get a grouped changelog + semver suggestion; LLM polish is
optional and advisory.
"""

from __future__ import annotations

import gradio as gr

from .release_notes import (
    build_notes,
    collect_git_log,
    current_version_from_pyproject,
    polish_markdown,
    render_markdown,
)
from .release_notes.report import normalize_lang

_I18N = {
    "en": {
        "title": "## 🚀 Release Notes\n"
                 "Grouped changelog from conventional commits "
                 "(`type(scope)!: subject`) plus a semver bump suggestion "
                 "(breaking → major, feat → minor, else patch). "
                 "Deterministic; the LLM polish pass is optional.",
        "log_label": "Commit log (sha<TAB>subject per line)",
        "log_ph": "a1b2c3d\tfeat(ui): two-level hub\n"
                  "d4e5f6a\tfix: handle empty config…",
        "repo_btn": "Load from this repo (since last tag)",
        "version_label": "Current version (optional)",
        "polish_label": "LLM polish (needs an API key)",
        "gen_btn": "Generate notes",
        "report_ph": "▶ The grouped changelog and version suggestion "
                     "appear here.",
        "empty_log": "⚠️ Paste a commit log first.",
    },
    "zh": {
        "title": "## 🚀 发布助手\n"
                 "按 conventional commits(`type(scope)!: subject`)分组生成 "
                 "changelog,并给出语义化版本建议(breaking → major,feat → "
                 "minor,否则 patch)。确定性生成;LLM 润色可选。",
        "log_label": "提交记录(每行 sha<TAB>subject)",
        "log_ph": "a1b2c3d\tfeat(ui): two-level hub\n"
                  "d4e5f6a\tfix: handle empty config…",
        "repo_btn": "读取本仓库(自上个 tag 起)",
        "version_label": "当前版本(可选)",
        "polish_label": "LLM 润色(需配置 API key)",
        "gen_btn": "生成发布说明",
        "report_ph": "▶ 生成后在此显示分组 changelog 与版本建议。",
        "empty_log": "⚠️ 请先粘贴提交记录。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_release_notes_page(app: gr.Blocks) -> None:
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
                log_box = gr.Textbox(label=t("log_label"),
                                     placeholder=t("log_ph"), lines=12)
                repo_btn = gr.Button(t("repo_btn"), size="sm")
                version_box = gr.Textbox(label=t("version_label"),
                                         value=current_version_from_pyproject())
                polish_cb = gr.Checkbox(label=t("polish_label"), value=False)
                gen_btn = gr.Button(t("gen_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-fmt-main"]):
                report_md = gr.Markdown(t("report_ph"))

    # ── callbacks ──

    def do_load_repo():
        try:
            return collect_git_log(".")
        except Exception as exc:  # noqa: BLE001 — git missing/not a repo
            return f"# {type(exc).__name__}: {exc}"

    def do_generate(log_text: str, version: str, polish: bool, lang: str):
        lang = normalize_lang(lang)
        if not (log_text or "").strip():
            return _t(lang, "empty_log")
        try:
            notes = build_notes(log_text, version)
            md = render_markdown(notes, lang)
            if polish:
                md = polish_markdown(md, lang)
            return md
        except Exception as exc:  # noqa: BLE001 — never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "log_label"),
                      placeholder=_t(lang, "log_ph")),
            gr.update(value=_t(lang, "repo_btn")),
            gr.update(label=_t(lang, "version_label")),
            gr.update(label=_t(lang, "polish_label")),
            gr.update(value=_t(lang, "gen_btn")),
        )

    repo_btn.click(do_load_repo, outputs=[log_box])
    gen_btn.click(do_generate,
                  inputs=[log_box, version_box, polish_cb, lang_state],
                  outputs=[report_md])

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
        outputs=[lang_state, title_md, log_box, repo_btn, version_box,
                 polish_cb, gen_btn, report_md],
    )
