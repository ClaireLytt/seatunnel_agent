# -*- coding: utf-8 -*-
"""Gradio page for LLM cost observability.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("LLM Cost", "/llmcost")``.  Read-only over the local usage log —
no LLM call is ever made from this page.
"""

from __future__ import annotations

import gradio as gr

from .llm_cost import merged_prices, override_path, render_markdown, summarize_cost
from .llm_cost.i18n import normalize_lang
from .utils import cjk_font_family

_DAY_CHOICES = [7, 14, 30, 90]

_I18N = {
    "en": {
        "title": "## 💰 LLM Cost\n"
                 "Cost & usage dashboard over the cross-agent LLM call log — "
                 "every `LLMClient.chat` call is priced against an "
                 "approximate catalog you can override in "
                 "`~/.seatunnel-agent/pricing.yaml`.",
        "days_label": "Window (days)",
        "refresh_btn": "Refresh",
        "price_acc": "Price catalog",
        "price_note": "Override file: ",
        "chart_cost": "Cost per day (stacked by model)",
        "chart_tokens": "Tokens by model",
        "no_data": "No data to chart in this window.",
    },
    "zh": {
        "title": "## 💰 LLM 成本观测\n"
                 "基于全平台 LLM 调用日志的成本用量看板 — 每次 "
                 "`LLMClient.chat` 调用按近似价格表计价,价格可在 "
                 "`~/.seatunnel-agent/pricing.yaml` 覆盖。",
        "days_label": "时间窗(天)",
        "refresh_btn": "刷新",
        "price_acc": "价格表",
        "price_note": "覆盖文件: ",
        "chart_cost": "按日成本(按模型堆叠)",
        "chart_tokens": "按模型 tokens",
        "no_data": "该时间窗内没有可作图的数据。",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def _cost_figure(summary: dict, lang: str):
    """Stacked per-day cost bars, one segment per model."""
    by_day_model = summary.get("by_day_model") or {}
    if not by_day_model:
        return None
    from matplotlib.figure import Figure
    days = sorted(by_day_model)[-30:]
    models = sorted({m for d in days for m in by_day_model[d]})
    if not models:
        return None
    fig = Figure(figsize=(7, 3))
    ax = fig.subplots()
    bottom = [0.0] * len(days)
    palette = ["#7c3aed", "#0ea5e9", "#16a34a", "#f59e0b", "#e11d48",
               "#0d9488", "#6366f1", "#ca8a04"]
    for i, model in enumerate(models):
        vals = [by_day_model[d].get(model, 0.0) for d in days]
        ax.bar(days, vals, bottom=bottom, label=model,
               color=palette[i % len(palette)])
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_ylabel("USD")
    fam = cjk_font_family()
    ax.set_title(_t(lang, "chart_cost"),
                 **({"fontfamily": fam} if fam else {}))
    ax.legend(fontsize=7)
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(30)
        lbl.set_ha("right")
        lbl.set_fontsize(7)
    fig.tight_layout()
    return fig


def _tokens_figure(summary: dict, lang: str):
    by_model = summary.get("by_model") or {}
    if not by_model:
        return None
    from matplotlib.figure import Figure
    models = sorted(by_model, key=lambda m: -(by_model[m]["input"]
                                              + by_model[m]["output"]))[:8]
    fig = Figure(figsize=(7, 3))
    ax = fig.subplots()
    inp = [by_model[m]["input"] for m in models]
    out = [by_model[m]["output"] for m in models]
    ax.bar(models, inp, color="#0ea5e9", label="input")
    ax.bar(models, out, bottom=inp, color="#f59e0b", label="output")
    ax.set_ylabel("tokens")
    fam = cjk_font_family()
    ax.set_title(_t(lang, "chart_tokens"),
                 **({"fontfamily": fam} if fam else {}))
    ax.legend(fontsize=8)
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(20)
        lbl.set_ha("right")
        lbl.set_fontsize(7)
    fig.tight_layout()
    return fig


def _price_table_md(lang: str) -> str:
    zh = normalize_lang(lang) == "zh"
    try:
        entries = merged_prices()
    except ValueError as exc:
        return f"⚠️ {exc}"
    rows = ["| " + ("模型前缀 | 输入 $/M | 输出 $/M | 来源" if zh else
                    "Model prefix | Input $/M | Output $/M | Source") + " |",
            "|---|---|---|---|"]
    for e in entries:
        rows.append(f"| `{e.prefix}` | {e.input_usd} | {e.output_usd} "
                    f"| {e.source} |")
    note = _t(lang, "price_note") + f"`{override_path()}`"
    return note + "\n\n" + "\n".join(rows)


def render_llm_cost_page(app: gr.Blocks) -> None:
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
            days_dd = gr.Dropdown(choices=_DAY_CHOICES, value=30,
                                  label=t("days_label"), scale=0)
            refresh_btn = gr.Button(t("refresh_btn"), variant="primary",
                                    scale=0)

        summary_md = gr.Markdown("")
        cost_plot = gr.Plot(visible=False)
        tokens_plot = gr.Plot(visible=False)
        with gr.Accordion(t("price_acc"), open=False) as price_acc:
            price_md = gr.Markdown("")

    # ── callbacks ──

    def do_refresh(days: int, lang: str):
        lang = normalize_lang(lang)
        try:
            s = summarize_cost(int(days))
        except ValueError as exc:  # malformed pricing override
            return (f"⚠️ {exc}", gr.update(visible=False),
                    gr.update(visible=False), _price_table_md(lang))
        md = render_markdown(s, lang)
        try:
            fig_cost = _cost_figure(s, lang)
            fig_tok = _tokens_figure(s, lang)
        except Exception:  # noqa: BLE001 — charts are optional (matplotlib)
            fig_cost = fig_tok = None
        upd = lambda f: (gr.update(value=f, visible=True) if f is not None  # noqa: E731
                         else gr.update(visible=False))
        return md, upd(fig_cost), upd(fig_tok), _price_table_md(lang)

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "days_label")),
            gr.update(value=_t(lang, "refresh_btn")),
            gr.update(label=_t(lang, "price_acc")),
        )

    refresh_btn.click(do_refresh, inputs=[days_dd, lang_state],
                      outputs=[summary_md, cost_plot, tokens_plot, price_md])
    days_dd.change(do_refresh, inputs=[days_dd, lang_state],
                   outputs=[summary_md, cost_plot, tokens_plot, price_md])

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _on_load(request: gr.Request):
        lang, *updates = switch_lang(choice_from_request(request))
        return (lang, *updates, *do_refresh(30, lang))

    app.load(
        _on_load, inputs=None,
        outputs=[lang_state, title_md, days_dd, refresh_btn, price_acc,
                 summary_md, cost_plot, tokens_plot, price_md],
    )
