# -*- coding: utf-8 -*-
"""Gradio page for CI log triage.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("CI Log Triage", "/ciinspect")``.  Paste failed-job logs and/or
runs metadata JSON; everything is analyzed locally.
"""

from __future__ import annotations

import gradio as gr

from .ci_inspect import analyze, render_markdown
from .ci_inspect.report import normalize_lang

_I18N = {
    "en": {
        "title": "## 🧭 CI Log Triage\n"
                 "Cluster failed-job logs into Top-N root causes (numbers / "
                 "paths / hashes masked before grouping), and analyze runs "
                 "metadata for flaky jobs (same commit, both pass & fail) "
                 "and duration drift. Offline — paste what `gh run view "
                 "--log-failed` / `gh api .../actions/runs` gives you.",
        "log_label": "Failed job log",
        "log_ph": "Paste one job's log (GitHub Actions timestamps are fine)…",
        "name_label": "Job name",
        "runs_acc": "Runs metadata (flaky & duration)",
        "runs_label": "Runs JSON",
        "runs_ph": '[{"workflow":"tests","conclusion":"failure",'
                   '"head_sha":"abc1234","duration_s":312}, …]',
        "analyze_btn": "Analyze",
        "report_ph": "▶ Root-cause clusters, flaky jobs and duration drift "
                     "appear here.",
        "empty": "⚠️ Paste a log or runs JSON first.",
    },
    "zh": {
        "title": "## 🧭 CI 日志诊断\n"
                 "把失败作业日志聚类成 Top-N 根因(聚类前先掩掉数字 / 路径 / "
                 "哈希),并对运行元数据做 flaky 识别(同一提交又过又挂)与"
                 "时长漂移分析。全离线 — 粘贴 `gh run view --log-failed` / "
                 "`gh api .../actions/runs` 的输出即可。",
        "log_label": "失败作业日志",
        "log_ph": "粘贴一个作业的日志(带 GitHub Actions 时间戳也可以)…",
        "name_label": "作业名",
        "runs_acc": "运行元数据(flaky 与时长)",
        "runs_label": "Runs JSON",
        "runs_ph": '[{"workflow":"tests","conclusion":"failure",'
                   '"head_sha":"abc1234","duration_s":312}, …]',
        "analyze_btn": "分析",
        "report_ph": "▶ 分析后在此显示根因聚类、flaky 作业与时长漂移。",
        "empty": "⚠️ 请先粘贴日志或 runs JSON。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_ci_inspect_page(app: gr.Blocks) -> None:
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
                name_box = gr.Textbox(label=t("name_label"), value="job")
                log_box = gr.Textbox(label=t("log_label"),
                                     placeholder=t("log_ph"), lines=10)
                with gr.Accordion(t("runs_acc"), open=False) as runs_acc:
                    runs_box = gr.Textbox(label=t("runs_label"),
                                          placeholder=t("runs_ph"), lines=6)
                analyze_btn = gr.Button(t("analyze_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-fmt-main"]):
                report_md = gr.Markdown(t("report_ph"))

    # ── callbacks ──

    def do_analyze(name: str, log_text: str, runs_text: str, lang: str):
        lang = normalize_lang(lang)
        if not (log_text or "").strip() and not (runs_text or "").strip():
            return _t(lang, "empty")
        try:
            logs = ({(name or "job").strip(): log_text}
                    if (log_text or "").strip() else {})
            result = analyze(logs=logs, runs_text=runs_text)
            return render_markdown(result, lang)
        except Exception as exc:  # noqa: BLE001 — never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "name_label")),
            gr.update(label=_t(lang, "log_label"),
                      placeholder=_t(lang, "log_ph")),
            gr.update(label=_t(lang, "runs_acc")),
            gr.update(label=_t(lang, "runs_label"),
                      placeholder=_t(lang, "runs_ph")),
            gr.update(value=_t(lang, "analyze_btn")),
        )

    analyze_btn.click(do_analyze,
                      inputs=[name_box, log_box, runs_box, lang_state],
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
        outputs=[lang_state, title_md, name_box, log_box, runs_acc,
                 runs_box, analyze_btn, report_md],
    )
