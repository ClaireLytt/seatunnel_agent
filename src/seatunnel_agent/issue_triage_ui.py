# -*- coding: utf-8 -*-
"""Gradio page for the issue-triage agent — registered via its manifest."""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from .issue_triage import load_issues, render_markdown, triage
from .issue_triage.report import normalize_lang

_DEMO = (Path(__file__).resolve().parents[2] / "examples" / "triage_demo"
         / "issues.jsonl")

_I18N = {
    "en": {
        "title": "## 🏷️ Issue Triage Agent\n"
                 "Paste a new issue: the agent searches past issues for "
                 "duplicates (BM25), greps the codebase, checks the docs — "
                 "then proposes labels, priority and a draft reply. "
                 "History defaults to the bundled demo; point the CLI at "
                 "your own JSONL.",
        "t_label": "Issue title",
        "b_label": "Issue body",
        "run_btn": "Triage",
        "report_ph": "▶ Labels, duplicates, priority and the draft reply "
                     "appear here.",
        "empty": "⚠️ Type a title first.",
        "no_key": "⚠️ No LLM configured — set an API key on /settings.",
    },
    "zh": {
        "title": "## 🏷️ Issue 分诊 Agent\n"
                 "粘贴一条新 issue:agent 自己在历史 issue 里查重(BM25)、"
                 "grep 代码定位模块、查文档,然后给出标签、优先级与草拟"
                 "回复。历史默认用内置 demo;CLI 可指定你自己的 JSONL。",
        "t_label": "Issue 标题",
        "b_label": "Issue 正文",
        "run_btn": "分诊",
        "report_ph": "▶ 标签、疑似重复、优先级与草拟回复在此显示。",
        "empty": "⚠️ 请先输入标题。",
        "no_key": "⚠️ 未配置 LLM — 请先到 /settings 配置 API key。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def _llm_ready() -> bool:
    import os
    return bool(os.getenv("API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", ""))


def render_issue_triage_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-fmt-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-fmt-side"]):
                t_box = gr.Textbox(label=t("t_label"))
                b_box = gr.Textbox(label=t("b_label"), lines=8)
                run_btn = gr.Button(t("run_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-fmt-main"]):
                report_md = gr.Markdown(t("report_ph"))

    def do_triage(title: str, body: str, lang: str):
        lang = normalize_lang(lang)
        if not (title or "").strip():
            return _t(lang, "empty")
        if not _llm_ready():
            return _t(lang, "no_key")
        try:
            from dotenv import load_dotenv

            from . import settings_store
            from .config import load_settings
            load_dotenv()
            settings_store.apply_to_env()
            issues = load_issues(_DEMO) if _DEMO.is_file() else []
            result = triage(title, body, load_settings(), issues=issues,
                            repo_dir=".")
            return render_markdown(result, lang)
        except Exception as exc:  # noqa: BLE001 — never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "t_label")),
            gr.update(label=_t(lang, "b_label")),
            gr.update(value=_t(lang, "run_btn")),
        )

    run_btn.click(do_triage, inputs=[t_box, b_box, lang_state],
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
        outputs=[lang_state, title_md, t_box, b_box, run_btn, report_md],
    )
