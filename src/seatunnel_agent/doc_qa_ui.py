# -*- coding: utf-8 -*-
"""Gradio page for doc Q&A — registered via the plugin manifest."""

from __future__ import annotations

import gradio as gr

from .doc_qa import answer, get_index
from .doc_qa.answer import normalize_lang

_I18N = {
    "en": {
        "title": "## 📖 Doc Q&A\n"
                 "Ask about SeaTunnel connectors and this project's docs — "
                 "offline BM25 retrieval with citations; tick the LLM box "
                 "for a synthesized answer grounded in the retrieved "
                 "excerpts only.",
        "q_label": "Question",
        "q_ph": "e.g. How do I configure the Jdbc sink batch size?",
        "llm_label": "LLM synthesis (needs an API key)",
        "ask_btn": "Ask",
        "report_ph": "▶ The answer and its sources appear here.",
        "empty": "⚠️ Type a question first.",
    },
    "zh": {
        "title": "## 📖 文档问答\n"
                 "询问 SeaTunnel 连接器与本项目文档 — 离线 BM25 检索,"
                 "带来源引用;勾选 LLM 可基于检索片段综合作答(只依据"
                 "片段,不编造参数)。",
        "q_label": "问题",
        "q_ph": "例如:Jdbc sink 的批量写入参数怎么配?",
        "llm_label": "LLM 综合作答(需 API key)",
        "ask_btn": "提问",
        "report_ph": "▶ 回答与来源在此显示。",
        "empty": "⚠️ 请先输入问题。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_doc_qa_page(app: gr.Blocks) -> None:
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
                q_box = gr.Textbox(label=t("q_label"),
                                   placeholder=t("q_ph"), lines=4)
                llm_cb = gr.Checkbox(label=t("llm_label"), value=False)
                ask_btn = gr.Button(t("ask_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-fmt-main"]):
                report_md = gr.Markdown(t("report_ph"))

    # ── callbacks ──

    def do_ask(question: str, use_llm: bool, lang: str):
        lang = normalize_lang(lang)
        if not (question or "").strip():
            return _t(lang, "empty")
        try:
            return answer(question, get_index(), lang=lang,
                          use_llm=use_llm)["markdown"]
        except Exception as exc:  # noqa: BLE001 — never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "q_label"),
                      placeholder=_t(lang, "q_ph")),
            gr.update(label=_t(lang, "llm_label")),
            gr.update(value=_t(lang, "ask_btn")),
        )

    ask_btn.click(do_ask, inputs=[q_box, llm_cb, lang_state],
                  outputs=[report_md])
    q_box.submit(do_ask, inputs=[q_box, llm_cb, lang_state],
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
        outputs=[lang_state, title_md, q_box, llm_cb, ask_btn, report_md],
    )
