# -*- coding: utf-8 -*-
"""Gradio page for the Prompt Lab.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Prompt Lab", "/promptlab")``.  Runs one prompt across the
provider profiles saved on the /settings page and compares the outputs.
"""

from __future__ import annotations

import gradio as gr

from .prompt_lab import (
    ACTIVE,
    ExperimentLogger,
    render_diff,
    render_matrix_markdown,
    run_matrix,
)
from .prompt_lab.report import normalize_lang
from .settings_store import list_profiles

_I18N = {
    "en": {
        "title": "## 🧪 Prompt Lab\n"
                 "Run one prompt across several provider profiles "
                 "side-by-side — outputs, tokens, latency and diff. Profiles "
                 "are saved on the Settings page; `(active)` is the "
                 "currently configured LLM. Experiments never switch the "
                 "app's active provider.",
        "prompt_label": "Prompt",
        "prompt_ph": "The user prompt to send to every profile…",
        "system_label": "System prompt (optional)",
        "system_ph": "Defaults to a plain assistant persona",
        "profiles_label": "Profiles",
        "profiles_hint": "No saved profiles yet? Save one per provider on "
                         "the [Settings](/settings) page, then reload this "
                         "page.",
        "report_ph": "▶ Results appear here after a run — per-profile "
                     "outputs with tokens and latency, ready to diff.",
        "parallel_label": "Run in parallel",
        "run_btn": "Run matrix",
        "diff_acc": "Diff two profiles",
        "diff_a": "From",
        "diff_b": "To",
        "diff_btn": "Diff",
        "hist_acc": "Experiment history",
        "hist_btn": "Refresh history",
        "empty_prompt": "⚠️ Type a prompt first.",
        "no_profiles": "⚠️ Select at least one profile.",
        "need_two": "⚠️ Run a matrix with ≥2 successful cells first.",
        "no_history": "No experiments logged yet.",
    },
    "zh": {
        "title": "## 🧪 Prompt 实验室\n"
                 "同一个 Prompt 在多个模型档案上并排运行 — 对比输出、"
                 "token、耗时与差异。档案在「设置」页保存;`(active)` 表示"
                 "当前生效的 LLM。实验不会切换全局配置。",
        "prompt_label": "Prompt",
        "prompt_ph": "发给每个档案的用户 Prompt…",
        "system_label": "System Prompt(可选)",
        "system_ph": "默认使用通用助手人设",
        "profiles_label": "模型档案",
        "profiles_hint": "还没有档案?在 [设置](/settings) 页按 provider "
                         "各存一份档案,回来刷新本页即可多选对比。",
        "report_ph": "▶ 运行后在此显示结果 — 各档案的输出、token 与耗时,"
                     "可随后两两对比差异。",
        "parallel_label": "并行执行",
        "run_btn": "运行对比",
        "diff_acc": "对比两个档案的输出",
        "diff_a": "基准",
        "diff_b": "对比",
        "diff_btn": "生成差异",
        "hist_acc": "实验历史",
        "hist_btn": "刷新历史",
        "empty_prompt": "⚠️ 请先输入 Prompt。",
        "no_profiles": "⚠️ 至少选择一个档案。",
        "need_two": "⚠️ 请先运行一次含 ≥2 个成功结果的对比。",
        "no_history": "还没有实验记录。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def _profile_choices() -> list[str]:
    try:
        return [ACTIVE] + list_profiles()
    except Exception:  # noqa: BLE001 — a broken store must not kill the page
        return [ACTIVE]


def _history_md(lang: str) -> str:
    recs = ExperimentLogger().recent(20)
    if not recs:
        return _t(lang, "no_history")
    zh = normalize_lang(lang) == "zh"
    rows = ["| " + ("时间 | Prompt | 档案 | 结果" if zh
                    else "Time | Prompt | Profiles | Cells") + " |",
            "|---|---|---|---|"]
    for r in reversed(recs):
        cells = r.get("cells", [])
        ok = sum(1 for c in cells if not c.get("error"))
        profs = ", ".join(c.get("profile", "?") for c in cells)
        preview = (r.get("prompt_preview") or "").replace("|", "\\|")[:60]
        rows.append(f"| {r.get('ts', '')[:16]} | {preview} | {profs} "
                    f"| {ok}/{len(cells)} ✓ |")
    return "\n".join(rows)


def render_prompt_lab_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)
    matrix_state = gr.State(None)  # last MatrixResult

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-fmt-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-fmt-side"]):
                prompt_box = gr.Textbox(label=t("prompt_label"),
                                        placeholder=t("prompt_ph"), lines=6)
                system_box = gr.Textbox(label=t("system_label"),
                                        placeholder=t("system_ph"), lines=2)
                profiles_cg = gr.CheckboxGroup(
                    choices=_profile_choices(), value=[ACTIVE],
                    label=t("profiles_label"))
                profiles_hint_md = gr.Markdown(
                    t("profiles_hint"), elem_classes=["st-dim-hint"],
                    visible=len(_profile_choices()) <= 1)
                parallel_cb = gr.Checkbox(label=t("parallel_label"),
                                          value=True)
                run_btn = gr.Button(t("run_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-fmt-main"]):
                report_md = gr.Markdown(t("report_ph"))
                with gr.Accordion(t("diff_acc"), open=False) as diff_acc:
                    with gr.Row():
                        diff_a_dd = gr.Dropdown(choices=[], label=t("diff_a"))
                        diff_b_dd = gr.Dropdown(choices=[], label=t("diff_b"))
                        diff_btn = gr.Button(t("diff_btn"), size="sm")
                    diff_md = gr.Markdown("")
                with gr.Accordion(t("hist_acc"), open=False) as hist_acc:
                    hist_md = gr.Markdown("")
                    hist_btn = gr.Button(t("hist_btn"), size="sm")

    # ── callbacks ──

    def do_run(prompt: str, system: str, profiles: list[str],
               parallel: bool, lang: str):
        lang = normalize_lang(lang)
        no_dd = gr.update(choices=[], value=None)
        if not (prompt or "").strip():
            return _t(lang, "empty_prompt"), None, no_dd, no_dd
        if not profiles:
            return _t(lang, "no_profiles"), None, no_dd, no_dd
        try:
            result = run_matrix(prompt, system=system, profiles=profiles,
                                parallel=parallel)
        except Exception as exc:  # noqa: BLE001 — never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}", None, no_dd, no_dd
        ok = [c.profile for c in result.cells if not c.error]
        dd_a = gr.update(choices=ok, value=ok[0] if ok else None)
        dd_b = gr.update(choices=ok, value=ok[1] if len(ok) > 1 else None)
        return render_matrix_markdown(result, lang), result, dd_a, dd_b

    def do_diff(result, a: str, b: str, lang: str):
        lang = normalize_lang(lang)
        if result is None or not a or not b:
            return _t(lang, "need_two")
        cells = {c.profile: c for c in result.cells}
        if a not in cells or b not in cells:
            return _t(lang, "need_two")
        return render_diff(cells[a], cells[b], lang)

    def do_history(lang: str):
        return _history_md(normalize_lang(lang))

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        choices = _profile_choices()
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "prompt_label"),
                      placeholder=_t(lang, "prompt_ph")),
            gr.update(label=_t(lang, "system_label"),
                      placeholder=_t(lang, "system_ph")),
            gr.update(label=_t(lang, "profiles_label"), choices=choices),
            gr.update(value=_t(lang, "profiles_hint"),
                      visible=len(choices) <= 1),
            gr.update(label=_t(lang, "parallel_label")),
            gr.update(value=_t(lang, "run_btn")),
            gr.update(label=_t(lang, "diff_acc")),
            gr.update(label=_t(lang, "diff_a")),
            gr.update(label=_t(lang, "diff_b")),
            gr.update(value=_t(lang, "diff_btn")),
            gr.update(label=_t(lang, "hist_acc")),
            gr.update(value=_t(lang, "hist_btn")),
        )

    run_btn.click(do_run,
                  inputs=[prompt_box, system_box, profiles_cg, parallel_cb,
                          lang_state],
                  outputs=[report_md, matrix_state, diff_a_dd, diff_b_dd])
    diff_btn.click(do_diff,
                   inputs=[matrix_state, diff_a_dd, diff_b_dd, lang_state],
                   outputs=[diff_md])
    hist_btn.click(do_history, inputs=[lang_state], outputs=[hist_md])

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _on_load(current_report: str, request: gr.Request):
        lang, *updates = switch_lang(choice_from_request(request))
        placeholders = {_t("zh", "report_ph"), _t("en", "report_ph"), ""}
        rep_upd = (gr.update(value=_t(lang, "report_ph"))
                   if (current_report or "").strip() in placeholders
                   else gr.update())
        return (lang, *updates, _history_md(lang), rep_upd)

    app.load(
        _on_load, inputs=[report_md],
        outputs=[lang_state, title_md, prompt_box, system_box, profiles_cg,
                 profiles_hint_md, parallel_cb, run_btn, diff_acc, diff_a_dd,
                 diff_b_dd, diff_btn, hist_acc, hist_btn, hist_md, report_md],
    )
