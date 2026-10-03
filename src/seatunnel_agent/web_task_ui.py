# -*- coding: utf-8 -*-
"""Gradio page for the web-task agent — registered via its manifest."""

from __future__ import annotations

import queue
import threading

import gradio as gr

from .web_task import run_task


def _norm(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


_I18N = {
    "en": {
        "title": "## 🖱️ Web Task Agent\n"
                 "Give it a goal and a start URL: the agent drives a real "
                 "(headless) browser — snapshot of the numbered interactive "
                 "elements → click/fill → observe again. Navigation is "
                 "confined to the start URL's origin. Try it on this "
                 "platform's own pages.",
        "goal_label": "Goal",
        "goal_ph": "e.g. open the SQL Formatter page and format SELECT 1",
        "url_label": "Start URL",
        "steps_label": "Max steps",
        "run_btn": "Run task",
        "report_ph": "▶ Actions stream here; the agent ends with "
                     "DONE/FAILED.",
        "empty": "⚠️ Provide a goal and a URL first.",
        "no_key": "⚠️ No LLM configured — set an API key on /settings.",
        "step_line": "🖱️ {i}. `{tool}` {inp} · {ms} ms{err}",
    },
    "zh": {
        "title": "## 🖱️ 网页操作 Agent\n"
                 "给目标和起始 URL:agent 驱动一个真实(无头)浏览器 — "
                 "获取编号元素快照 → 点击/填表 → 再观察。导航默认限制在"
                 "起始同源。可以拿本平台自己的页面试。",
        "goal_label": "任务目标",
        "goal_ph": "例如:打开 SQL 格式化页,把 SELECT 1 格式化一次",
        "url_label": "起始 URL",
        "steps_label": "步数上限",
        "run_btn": "执行任务",
        "report_ph": "▶ 操作步骤实时显示;结束时给出 DONE/FAILED。",
        "empty": "⚠️ 请先填写目标与 URL。",
        "no_key": "⚠️ 未配置 LLM — 请先到 /settings 配置 API key。",
        "step_line": "🖱️ {i}. `{tool}` {inp} · {ms} ms{err}",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[_norm(lang)].get(key, key)


def _llm_ready() -> bool:
    import os
    return bool(os.getenv("API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", ""))


def render_web_task_page(app: gr.Blocks) -> None:
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
                goal_box = gr.Textbox(label=t("goal_label"),
                                      placeholder=t("goal_ph"), lines=3)
                url_box = gr.Textbox(label=t("url_label"),
                                     value="http://127.0.0.1:7860/")
                steps_num = gr.Slider(4, 25, value=15, step=1,
                                      label=t("steps_label"))
                run_btn = gr.Button(t("run_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-fmt-main"]):
                report_md = gr.Markdown(t("report_ph"))

    def do_run(goal: str, url: str, max_steps: float, lang: str):
        lang = _norm(lang)
        if not (goal or "").strip() or not (url or "").strip():
            yield _t(lang, "empty")
            return
        if not _llm_ready():
            yield _t(lang, "no_key")
            return
        from dotenv import load_dotenv

        from . import settings_store
        from .config import load_settings
        load_dotenv()
        settings_store.apply_to_env()

        events: queue.Queue = queue.Queue()
        outcome: dict = {}

        def worker():
            try:
                outcome["result"] = run_task(
                    goal.strip(), url.strip(), load_settings(),
                    max_steps=int(max_steps), on_step=events.put)
            except Exception as exc:  # noqa: BLE001
                outcome["error"] = f"{type(exc).__name__}: {exc}"
            events.put(None)

        threading.Thread(target=worker, daemon=True).start()
        lines: list[str] = []
        i = 0
        while True:
            step = events.get()
            if step is None:
                break
            i += 1
            inp = ", ".join(f"{k}={v!r}" for k, v in
                            list(step.input.items())[:2])
            lines.append(_t(lang, "step_line").format(
                i=i, tool=step.tool, inp=f"({inp})" if inp else "",
                ms=step.elapsed_ms, err=" · ⚠️" if step.error else ""))
            yield "\n\n".join(lines)
        if "error" in outcome:
            yield "\n\n".join(lines) + f"\n\n⚠️ {outcome['error']}"
        else:
            r = outcome["result"]
            mark = "✅" if r.success else "❌"
            yield ("\n\n".join(lines)
                   + f"\n\n---\n\n{mark} {r.reply}")

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "goal_label"),
                      placeholder=_t(lang, "goal_ph")),
            gr.update(label=_t(lang, "url_label")),
            gr.update(label=_t(lang, "steps_label")),
            gr.update(value=_t(lang, "run_btn")),
        )

    run_btn.click(do_run,
                  inputs=[goal_box, url_box, steps_num, lang_state],
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
        outputs=[lang_state, title_md, goal_box, url_box, steps_num,
                 run_btn, report_md],
    )
