# -*- coding: utf-8 -*-
"""Gradio page for the agent orchestrator.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Orchestrator", "/orchestrator")``.  One chat entry: the LLM
routes each request to the deterministic agents and chains steps; tool calls
show up as collapsible messages.  Without an API key the page degrades to
keyword suggestions.
"""

from __future__ import annotations

import gradio as gr

from .orchestrator import Orchestrator, build_catalog, render_suggestions, suggest
from .orchestrator.report import normalize_lang

_I18N = {
    "en": {
        "title": "## 🤖 Agent Orchestrator\n"
                 "One chat entry for the whole platform — describe what you "
                 "need (paste SQL / configs / DDL right in the message) and "
                 "the LLM routes it to the right agents, chaining steps when "
                 "needed.",
        "input_ph": "e.g. Review this SQL and then format it: SELECT …",
        "send_btn": "Send",
        "clear_btn": "New session",
        "agents_acc": "Routable agents",
        "no_key": "⚠️ No LLM configured — suggestions only. "
                  "Configure an API key on the [Settings](/settings) page.",
        "step_label": "🔧 {tool} · {ms} ms",
        "empty": "⚠️ Type a request first.",
    },
    "zh": {
        "title": "## 🤖 智能编排\n"
                 "全平台统一对话入口 — 描述你的需求(SQL / 配置 / DDL 直接"
                 "贴在消息里),LLM 自动路由到合适的 agent,需要时自动串联"
                 "多步。",
        "input_ph": "例如:帮我审查这段 SQL 然后格式化:SELECT …",
        "send_btn": "发送",
        "clear_btn": "新会话",
        "agents_acc": "可路由的 agent",
        "no_key": "⚠️ 未配置 LLM — 仅能做关键词推荐。"
                  "请到 [设置](/settings) 页配置 API key。",
        "step_label": "🔧 {tool} · {ms} ms",
        "empty": "⚠️ 请先输入需求。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def _agents_md(lang: str) -> str:
    zh = normalize_lang(lang) == "zh"
    try:
        catalog = build_catalog(default_lang=lang)
    except Exception as exc:  # noqa: BLE001 — the list must not kill the page
        return f"⚠️ {exc}"
    rows = ["| " + ("Agent | 页面 | 说明" if zh else "Agent | Page | What it does")
            + " |", "|---|---|---|"]
    for spec in sorted(catalog.values(), key=lambda s: s.name):
        page = f"[`{spec.page}`]({spec.page})" if spec.page else "—"
        rows.append(f"| `{spec.name}` | {page} | {spec.description[:110]} |")
    return "\n".join(rows)


def _llm_ready() -> bool:
    import os
    return bool(os.getenv("API_KEY", "")
                or os.getenv("ANTHROPIC_API_KEY", ""))


def render_orchestrator_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)
    orch_state = gr.State(None)  # per-session Orchestrator (multi-turn)

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-fmt-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])
        banner_md = gr.Markdown(visible=False)

        chatbot = gr.Chatbot(show_label=False, layout="panel",
                             buttons=["copy"], height=440,
                             elem_classes=["st-chatbot"])
        with gr.Row():
            input_box = gr.Textbox(placeholder=t("input_ph"), lines=3,
                                   scale=8, show_label=False)
            with gr.Column(scale=1, min_width=90):
                send_btn = gr.Button(t("send_btn"), variant="primary")
                clear_btn = gr.Button(t("clear_btn"), size="sm")

        with gr.Accordion(t("agents_acc"), open=False) as agents_acc:
            agents_md = gr.Markdown("")

    # ── callbacks ──

    def do_send(text: str, history: list, orch, lang: str):
        lang = normalize_lang(lang)
        history = list(history or [])
        text = (text or "").strip()
        if not text:
            return history, orch, ""
        history.append({"role": "user", "content": text})

        if not _llm_ready():
            catalog = build_catalog(default_lang=lang)
            reply = (_t(lang, "no_key") + "\n\n"
                     + render_suggestions(suggest(text, catalog), lang))
            history.append({"role": "assistant", "content": reply})
            return history, orch, ""

        try:
            if orch is None or getattr(orch, "lang", None) != lang:
                from .config import load_settings
                orch = Orchestrator(load_settings(), lang=lang)
            result = orch.run(text)
        except Exception as exc:  # noqa: BLE001 — never crash the page
            history.append({"role": "assistant",
                            "content": f"⚠️ {type(exc).__name__}: {exc}"})
            return history, orch, ""

        for s in result.steps:
            label = _t(lang, "step_label").format(tool=s.tool,
                                                  ms=s.elapsed_ms)
            body = s.output if len(s.output) < 4000 \
                else s.output[:4000] + "\n…"
            history.append({
                "role": "assistant",
                "content": f"<details><summary>{label}</summary>\n\n"
                           f"{body}\n\n</details>",
            })
        history.append({"role": "assistant",
                        "content": result.reply or "_(empty)_"})
        return history, orch, ""

    def do_clear():
        return [], None

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(visible=not _llm_ready(),
                      value=_t(lang, "no_key")),
            gr.update(placeholder=_t(lang, "input_ph")),
            gr.update(value=_t(lang, "send_btn")),
            gr.update(value=_t(lang, "clear_btn")),
            gr.update(label=_t(lang, "agents_acc")),
            _agents_md(lang),
        )

    send_btn.click(do_send,
                   inputs=[input_box, chatbot, orch_state, lang_state],
                   outputs=[chatbot, orch_state, input_box])
    input_box.submit(do_send,
                     inputs=[input_box, chatbot, orch_state, lang_state],
                     outputs=[chatbot, orch_state, input_box])
    clear_btn.click(do_clear, outputs=[chatbot, orch_state])

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, banner_md, input_box, send_btn,
                 clear_btn, agents_acc, agents_md],
    )
