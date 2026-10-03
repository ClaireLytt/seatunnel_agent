# -*- coding: utf-8 -*-
"""Gradio page for the code-fix agent — registered via its plugin manifest."""

from __future__ import annotations

import queue
import threading

import gradio as gr

from .code_fix import fix, render_markdown
from .code_fix.report import normalize_lang

_I18N = {
    "en": {
        "title": "## 🩹 Code Fix Agent\n"
                 "Point it at a git repo with failing tests: it runs pytest, "
                 "reads the code, patches, and re-runs until green — inside "
                 "a fresh **git worktree** (your checkout is never touched); "
                 "success is verified by a final deterministic run and the "
                 "diff is yours to review.",
        "path_label": "Repository path (must be a git repo)",
        "tests_label": "Test selector (optional)",
        "tests_ph": "e.g. tests/test_core.py::test_div",
        "inst_label": "Extra instruction (optional)",
        "steps_label": "Max steps",
        "run_btn": "Fix it",
        "report_ph": "▶ Agent steps stream here; the diff and verdict land "
                     "at the end.",
        "empty": "⚠️ Provide a repository path first.",
        "no_key": "⚠️ No LLM configured — set an API key on /settings.",
        "step_line": "🔧 {i}. `{tool}` · {ms} ms{err}",
    },
    "zh": {
        "title": "## 🩹 测试自愈 Agent\n"
                 "指向一个测试失败的 git 仓库:它自己跑 pytest、读码、打补丁、"
                 "复跑直到通过 — 全程在新建的 **git worktree** 里(你的工作区"
                 "绝不被改动);是否成功以最终的确定性复跑为准,diff 供人工"
                 "审阅采纳。",
        "path_label": "仓库路径(必须是 git 仓库)",
        "tests_label": "测试选择器(可选)",
        "tests_ph": "如 tests/test_core.py::test_div",
        "inst_label": "补充说明(可选)",
        "steps_label": "步数上限",
        "run_btn": "开始修复",
        "report_ph": "▶ Agent 步骤实时显示在此;结束后给出 diff 与验收结论。",
        "empty": "⚠️ 请先填写仓库路径。",
        "no_key": "⚠️ 未配置 LLM — 请先到 /settings 配置 API key。",
        "step_line": "🔧 {i}. `{tool}` · {ms} ms{err}",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def _llm_ready() -> bool:
    import os
    return bool(os.getenv("API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", ""))


def render_code_fix_page(app: gr.Blocks) -> None:
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
                path_box = gr.Textbox(label=t("path_label"))
                tests_box = gr.Textbox(label=t("tests_label"),
                                       placeholder=t("tests_ph"))
                inst_box = gr.Textbox(label=t("inst_label"), lines=2)
                steps_num = gr.Slider(4, 20, value=12, step=1,
                                      label=t("steps_label"))
                run_btn = gr.Button(t("run_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-fmt-main"]):
                report_md = gr.Markdown(t("report_ph"))

    # ── callbacks ──

    def do_fix(path: str, tests: str, inst: str, max_steps: float,
               lang: str):
        lang = normalize_lang(lang)
        if not (path or "").strip():
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
                outcome["result"] = fix(
                    path.strip(), load_settings(), tests=tests.strip(),
                    instruction=inst, max_steps=int(max_steps),
                    on_step=events.put)
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
            lines.append(_t(lang, "step_line").format(
                i=i, tool=step.tool, ms=step.elapsed_ms,
                err=" · ⚠️" if step.error else ""))
            yield "\n\n".join(lines)
        if "error" in outcome:
            yield "\n\n".join(lines) + f"\n\n⚠️ {outcome['error']}"
        else:
            yield render_markdown(outcome["result"], lang)

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "path_label")),
            gr.update(label=_t(lang, "tests_label"),
                      placeholder=_t(lang, "tests_ph")),
            gr.update(label=_t(lang, "inst_label")),
            gr.update(label=_t(lang, "steps_label")),
            gr.update(value=_t(lang, "run_btn")),
        )

    run_btn.click(do_fix,
                  inputs=[path_box, tests_box, inst_box, steps_num,
                          lang_state],
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
        outputs=[lang_state, title_md, path_box, tests_box, inst_box,
                 steps_num, run_btn, report_md],
    )
