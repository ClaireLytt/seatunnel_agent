# -*- coding: utf-8 -*-
"""Gradio page for the LLM eval harness.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("LLM Eval", "/llmeval")``.  Paste or load a YAML suite, run it
against the configured LLM, inspect per-case results and the score trend.
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from .llm_eval import RunLogger, compare, parse_suite, render_markdown, run_suite
from .llm_eval.report import normalize_lang

_DEMO_SUITE = (Path(__file__).resolve().parents[2] / "examples"
               / "llmeval_demo" / "text2sql_golden.yaml")

_I18N = {
    "en": {
        "title": "## 📏 LLM Eval\n"
                 "Golden suites for the platform's LLM features — the suite "
                 "runs against the configured LLM, deterministic checkers "
                 "score every case, and history powers the regression gate "
                 "(`seatunnel-agent llmeval --fail-on regression`).",
        "suite_label": "Suite (YAML)",
        "suite_ph": "suite: my-golden\ncases:\n  - id: t1\n    agent: raw_prompt\n    ...",
        "demo_btn": "Load demo suite",
        "judge_label": "Run judge checks (advisory)",
        "run_btn": "Run suite",
        "trend_acc": "Score trend",
        "trend_btn": "Refresh trend",
        "empty_suite": "⚠️ Paste a YAML suite first.",
        "no_runs": "No eval runs logged yet.",
        "running": "Running suite against the LLM…",
    },
    "zh": {
        "title": "## 📏 LLM 评测\n"
                 "平台 LLM 功能的黄金用例集 — 套件在当前配置的 LLM 上运行,"
                 "确定性检查器自动打分,历史记录支撑回归门禁"
                 "(`seatunnel-agent llmeval --fail-on regression`)。",
        "suite_label": "评测套件(YAML)",
        "suite_ph": "suite: my-golden\ncases:\n  - id: t1\n    agent: raw_prompt\n    ...",
        "demo_btn": "载入示例套件",
        "judge_label": "运行 judge 评分(仅参考)",
        "run_btn": "运行套件",
        "trend_acc": "分数趋势",
        "trend_btn": "刷新趋势",
        "empty_suite": "⚠️ 请先粘贴 YAML 套件。",
        "no_runs": "还没有评测运行记录。",
        "running": "正在用 LLM 运行套件…",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def _trend_figure(runs: list[dict]):
    if not runs:
        return None
    from matplotlib.figure import Figure
    # plain Figure (not pyplot) — no global registry to leak into
    by_suite: dict[str, list[tuple[str, float]]] = {}
    for r in runs:
        by_suite.setdefault(r.get("suite", "?"), []).append(
            (r.get("ts", "")[:16], float(r.get("score", 0.0))))
    fig = Figure(figsize=(7, 3))
    ax = fig.subplots()
    palette = ["#0ea5e9", "#7c3aed", "#16a34a", "#f59e0b", "#e11d48"]
    for i, (suite, pts) in enumerate(sorted(by_suite.items())):
        pts = pts[-20:]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o",
                label=suite, color=palette[i % len(palette)])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("score")
    from .utils import cjk_font_family
    fam = cjk_font_family()  # suite names in the legend may be Chinese
    ax.legend(fontsize=8, **({"prop": {"family": fam, "size": 8}}
                             if fam else {}))
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(30)
        lbl.set_ha("right")
        lbl.set_fontsize(7)
    fig.tight_layout()
    return fig


def render_llm_eval_page(app: gr.Blocks) -> None:
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
                suite_box = gr.Textbox(label=t("suite_label"),
                                       placeholder=t("suite_ph"), lines=16)
                with gr.Row():
                    demo_btn = gr.Button(t("demo_btn"), size="sm")
                    judge_cb = gr.Checkbox(label=t("judge_label"),
                                           value=False)
                run_btn = gr.Button(t("run_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-fmt-main"]):
                report_md = gr.Markdown("")
                with gr.Accordion(t("trend_acc"), open=False) as trend_acc:
                    trend_plot = gr.Plot(visible=False)
                    trend_btn = gr.Button(t("trend_btn"), size="sm")

    # ── callbacks ──

    def do_load_demo():
        try:
            return _DEMO_SUITE.read_text(encoding="utf-8")
        except OSError:
            return "suite: demo\ncases: []\n"

    def do_run(suite_yaml: str, judge: bool, lang: str):
        lang = normalize_lang(lang)
        if not (suite_yaml or "").strip():
            return _t(lang, "empty_suite")
        try:
            suite = parse_suite(suite_yaml)
            result = run_suite(suite, judge=judge)
            regression = compare(result,
                                 RunLogger().previous_run(suite.name))
            return render_markdown(result, lang, regression)
        except Exception as exc:  # noqa: BLE001 — never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"

    def do_trend(lang: str):
        lang = normalize_lang(lang)
        runs = RunLogger().recent(200)
        if not runs:
            return gr.update(visible=False)
        try:
            fig = _trend_figure(runs)
        except Exception:  # noqa: BLE001 — chart is optional (matplotlib)
            fig = None
        return (gr.update(value=fig, visible=True) if fig is not None
                else gr.update(visible=False))

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "suite_label"),
                      placeholder=_t(lang, "suite_ph")),
            gr.update(value=_t(lang, "demo_btn")),
            gr.update(label=_t(lang, "judge_label")),
            gr.update(value=_t(lang, "run_btn")),
            gr.update(label=_t(lang, "trend_acc")),
            gr.update(value=_t(lang, "trend_btn")),
        )

    demo_btn.click(do_load_demo, outputs=[suite_box])
    run_btn.click(do_run, inputs=[suite_box, judge_cb, lang_state],
                  outputs=[report_md])
    trend_btn.click(do_trend, inputs=[lang_state], outputs=[trend_plot])

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, suite_box, demo_btn, judge_cb,
                 run_btn, trend_acc, trend_btn],
    )
