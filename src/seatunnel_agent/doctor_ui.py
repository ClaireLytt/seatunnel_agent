# -*- coding: utf-8 -*-
"""Gradio page for the environment doctor — registered via its manifest."""

from __future__ import annotations

import gradio as gr

from .doctor import diagnose


def _norm(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


_I18N = {
    "en": {
        "title": "## 🩺 Environment Doctor\n"
                 "Describe what's wrong (\"the UI won't start\", \"LLM calls "
                 "time out\") — the agent inspects ports, packages, LLM "
                 "config and log tails (all read-only) and prescribes the "
                 "fix commands for YOU to run. Without an API key it prints "
                 "a full deterministic check-up instead.",
        "c_label": "Symptom",
        "c_ph": "e.g. seatunnel-agent ui exits immediately on port 7860",
        "run_btn": "Diagnose",
        "checkup_btn": "Full check-up (no LLM)",
        "report_ph": "▶ Diagnosis and prescribed commands appear here.",
        "empty": "⚠️ Describe the symptom first.",
    },
    "zh": {
        "title": "## 🩺 环境医生\n"
                 "描述症状(「UI 起不来」「LLM 调用超时」)— agent 自己检查"
                 "端口、依赖、LLM 配置与日志尾部(全只读),给出修复命令由"
                 "**你**执行。未配置 API key 时输出确定性全量体检报告。",
        "c_label": "症状描述",
        "c_ph": "例如:seatunnel-agent ui 在 7860 端口启动后立刻退出",
        "run_btn": "诊断",
        "checkup_btn": "全量体检(不调 LLM)",
        "report_ph": "▶ 诊断结论与修复命令在此显示。",
        "empty": "⚠️ 请先描述症状。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[_norm(lang)].get(key, key)


def _llm_ready() -> bool:
    import os
    return bool(os.getenv("API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", ""))


def render_doctor_page(app: gr.Blocks) -> None:
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
                c_box = gr.Textbox(label=t("c_label"),
                                   placeholder=t("c_ph"), lines=4)
                run_btn = gr.Button(t("run_btn"), variant="primary")
                checkup_btn = gr.Button(t("checkup_btn"), size="sm")

            with gr.Column(scale=5, elem_classes=["st-fmt-main"]):
                report_md = gr.Markdown(t("report_ph"))

    def do_diagnose(complaint: str, lang: str):
        lang = _norm(lang)
        if not (complaint or "").strip():
            return _t(lang, "empty")
        try:
            if not _llm_ready():
                return diagnose(complaint, settings=None, lang=lang).reply
            from dotenv import load_dotenv

            from . import settings_store
            from .config import load_settings
            load_dotenv()
            settings_store.apply_to_env()
            return diagnose(complaint, load_settings(), lang=lang).reply
        except Exception as exc:  # noqa: BLE001 — never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"

    def do_checkup(lang: str):
        return diagnose("checkup", settings=None, lang=_norm(lang)).reply

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "c_label"),
                      placeholder=_t(lang, "c_ph")),
            gr.update(value=_t(lang, "run_btn")),
            gr.update(value=_t(lang, "checkup_btn")),
        )

    run_btn.click(do_diagnose, inputs=[c_box, lang_state],
                  outputs=[report_md])
    checkup_btn.click(do_checkup, inputs=[lang_state], outputs=[report_md])

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
        outputs=[lang_state, title_md, c_box, run_btn, checkup_btn,
                 report_md],
    )
