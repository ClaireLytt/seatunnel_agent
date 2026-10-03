# -*- coding: utf-8 -*-
"""Gradio page for the agent orchestrator.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Orchestrator", "/orchestrator")``.  One chat entry: the LLM
routes each request to the deterministic agents and chains steps; tool calls
stream into the chat as they execute (worker thread + queue feeding a
generator callback).  Without an API key the page degrades to keyword
suggestions.
"""

from __future__ import annotations

import queue
import threading

import gradio as gr

from .orchestrator import Orchestrator, build_catalog, render_suggestions, suggest
from .orchestrator.olog import ChatLogger
from .orchestrator.report import normalize_lang

_I18N = {
    "en": {
        "title": "## 🤖 Agent Orchestrator\n"
                 "One chat entry for the whole platform — describe what you "
                 "need (paste SQL / configs / DDL right in the message) and "
                 "the LLM routes it to the right agents, chaining steps when "
                 "needed.",
        "chat_ph": "### 👋 What can I do?\n"
                   "Paste SQL / configs / DDL straight into the message — "
                   "I route it to the right agent: review, dialect "
                   "translation, impact analysis, skew check, formatting, "
                   "config lint, schema drift, PII scan, test data…\n\n"
                   "Steps chain automatically: *“translate to Doris, then "
                   "review the result”*.",
        "input_ph": "e.g. Review this SQL and then format it: SELECT …",
        "send_btn": "Send",
        "clear_btn": "New session",
        "agents_acc": "Routable agents",
        "no_key": "⚠️ No LLM configured — suggestions only. "
                  "Configure an API key on the [Settings](/settings) page.",
        "step_label": "🔧 {tool} · {ms} ms",
        "working": "⏳ Routing & running agents…",
        "ex_review": "Try: SQL review",
        "ex_chain": "Try: translate + review",
        "ex_pii": "Try: PII scan",
        "ex_review_text": "Review this SQL: SELECT * FROM dwd_order_df a, "
                          "dim_user_df b WHERE a.ds='2026-10-01'",
        "ex_chain_text": "Translate this Hive SQL to Doris, then review the "
                         "result: SELECT city, collect_set(user_id) FROM t "
                         "GROUP BY city",
        "ex_pii_text": "Any sensitive columns in this DDL? CREATE TABLE u "
                       "(phone STRING COMMENT 'mobile phone', id_card "
                       "STRING COMMENT 'national id')",
    },
    "zh": {
        "title": "## 🤖 智能编排\n"
                 "全平台统一对话入口 — 描述你的需求(SQL / 配置 / DDL 直接"
                 "贴在消息里),LLM 自动路由到合适的 agent,需要时自动串联"
                 "多步。",
        "chat_ph": "### 👋 我能做什么?\n"
                   "把 SQL / 配置 / DDL 直接贴进消息,我会路由到合适的 "
                   "agent:审查、方言翻译、影响分析、倾斜检测、格式化、"
                   "配置检查、Schema 漂移、PII 扫描、测试造数…\n\n"
                   "支持多步串联:*「翻译成 Doris,然后审查结果」*。",
        "input_ph": "例如:帮我审查这段 SQL 然后格式化:SELECT …",
        "send_btn": "发送",
        "clear_btn": "新会话",
        "agents_acc": "可路由的 agent",
        "no_key": "⚠️ 未配置 LLM — 仅能做关键词推荐。"
                  "请到 [设置](/settings) 页配置 API key。",
        "step_label": "🔧 {tool} · {ms} ms",
        "working": "⏳ 正在路由并执行 agent…",
        "ex_review": "示例:SQL 审查",
        "ex_chain": "示例:翻译+审查",
        "ex_pii": "示例:PII 扫描",
        "ex_review_text": "审查这段 SQL:SELECT * FROM dwd_order_df a, "
                          "dim_user_df b WHERE a.ds='2026-10-01'",
        "ex_chain_text": "把这段 Hive SQL 翻译成 Doris,然后审查翻译结果:"
                         "SELECT city, collect_set(user_id) FROM t "
                         "GROUP BY city",
        "ex_pii_text": "这段 DDL 里有敏感字段吗?CREATE TABLE u (phone "
                       "STRING COMMENT '手机号', id_card STRING "
                       "COMMENT '身份证')",
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
                             placeholder=t("chat_ph"),
                             elem_classes=["st-chatbot"])
        with gr.Row():
            input_box = gr.Textbox(placeholder=t("input_ph"), lines=3,
                                   scale=8, show_label=False)
            with gr.Column(scale=1, min_width=90):
                send_btn = gr.Button(t("send_btn"), variant="primary")
                clear_btn = gr.Button(t("clear_btn"), size="sm")
        with gr.Row():
            ex_review_btn = gr.Button(t("ex_review"), size="sm")
            ex_chain_btn = gr.Button(t("ex_chain"), size="sm")
            ex_pii_btn = gr.Button(t("ex_pii"), size="sm")

        with gr.Accordion(t("agents_acc"), open=False) as agents_acc:
            agents_md = gr.Markdown("")

    # ── callbacks ──

    def _plain_turns(history: list) -> list[tuple[str, str]]:
        """Displayed transcript → (role, text) pairs worth re-seeding:
        tool-step <details> blocks and transient indicators are skipped."""
        turns = []
        for m in history or []:
            content = str(m.get("content", ""))
            if content.startswith("<details>") or content.startswith("⏳"):
                continue
            turns.append((m.get("role", ""), content))
        return turns

    def _restore_display(lang: str) -> list[dict]:
        """Most recent persisted session → chatbot messages."""
        msgs: list[dict] = []
        for turn in ChatLogger().last_session():
            msgs.append({"role": "user", "content": turn.get("request", "")})
            reply = turn.get("reply", "")
            steps = turn.get("steps") or []
            if steps:
                used = ", ".join(f"`{s.get('tool')}`" for s in steps)
                reply = f"{reply}\n\n<sub>🔧 {used}</sub>"
            msgs.append({"role": "assistant", "content": reply})
        return msgs

    def _step_msg(step, lang: str) -> dict:
        label = _t(lang, "step_label").format(tool=step.tool,
                                              ms=step.elapsed_ms)
        body = step.output if len(step.output) < 4000 \
            else step.output[:4000] + "\n…"
        return {"role": "assistant",
                "content": f"<details><summary>{label}</summary>\n\n"
                           f"{body}\n\n</details>"}

    def do_send(text: str, history: list, orch, lang: str):
        """Generator: steps stream into the chat as the engine executes."""
        lang = normalize_lang(lang)
        history = list(history or [])
        text = (text or "").strip()
        if not text:
            yield history, orch, ""
            return
        history.append({"role": "user", "content": text})
        yield history, orch, ""  # echo immediately

        if not _llm_ready():
            catalog = build_catalog(default_lang=lang)
            reply = (_t(lang, "no_key") + "\n\n"
                     + render_suggestions(suggest(text, catalog), lang))
            history.append({"role": "assistant", "content": reply})
            yield history, orch, ""
            return

        try:
            if orch is None or getattr(orch, "lang", None) != lang:
                from .config import load_settings
                orch = Orchestrator(load_settings(), lang=lang)
                # page refresh lost the instance: rebuild context from the
                # displayed transcript (everything before this user turn)
                prior = _plain_turns(history[:-1])
                if prior:
                    orch.seed_transcript(prior)
        except Exception as exc:  # noqa: BLE001
            history.append({"role": "assistant",
                            "content": f"⚠️ {type(exc).__name__}: {exc}"})
            yield history, orch, ""
            return

        # pending indicator; steps are inserted before it as they arrive
        history.append({"role": "assistant", "content": _t(lang, "working")})
        pending = len(history) - 1
        yield history, orch, ""

        events: queue.Queue = queue.Queue()
        outcome: dict = {}

        def worker():
            try:
                outcome["result"] = orch.run(text, on_step=events.put)
            except Exception as exc:  # noqa: BLE001
                outcome["error"] = f"{type(exc).__name__}: {exc}"
            events.put(None)  # sentinel

        threading.Thread(target=worker, daemon=True).start()
        while True:
            step = events.get()
            if step is None:
                break
            history.insert(pending, _step_msg(step, lang))
            pending += 1
            yield history, orch, ""

        if "error" in outcome:
            history[pending] = {"role": "assistant",
                                "content": f"⚠️ {outcome['error']}"}
        else:
            result = outcome["result"]
            history[pending] = {"role": "assistant",
                                "content": result.reply or "_(empty)_"}
            ChatLogger().log_turn(orch.session_id, text, result.reply,
                                  [s.to_dict() for s in result.steps])
        yield history, orch, ""

    def do_clear():
        return [], None

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(visible=not _llm_ready(),
                      value=_t(lang, "no_key")),
            gr.update(placeholder=_t(lang, "chat_ph")),
            gr.update(placeholder=_t(lang, "input_ph")),
            gr.update(value=_t(lang, "send_btn")),
            gr.update(value=_t(lang, "clear_btn")),
            gr.update(value=_t(lang, "ex_review")),
            gr.update(value=_t(lang, "ex_chain")),
            gr.update(value=_t(lang, "ex_pii")),
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
    for btn, key in ((ex_review_btn, "ex_review_text"),
                     (ex_chain_btn, "ex_chain_text"),
                     (ex_pii_btn, "ex_pii_text")):
        btn.click((lambda k: lambda lang: _t(lang, k))(key),
                  inputs=[lang_state], outputs=[input_box])

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        lang, title, banner, chat_upd, *rest = switch_lang(
            choice_from_request(request))
        restored = _restore_display(lang)
        if restored:
            chat_upd = gr.update(placeholder=_t(lang, "chat_ph"),
                                 value=restored)
        return (lang, title, banner, chat_upd, *rest)

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, banner_md, chatbot, input_box,
                 send_btn, clear_btn, ex_review_btn, ex_chain_btn,
                 ex_pii_btn, agents_acc, agents_md],
    )
