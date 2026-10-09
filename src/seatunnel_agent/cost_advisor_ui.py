# -*- coding: utf-8 -*-
"""Gradio page for the query cost advisor.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("Cost", "/cost")``.  Recommendations only — computed from
the query audit log; no table is touched, nothing executed, no LLM.
"""

from __future__ import annotations

import gradio as gr

from .cost_advisor import analyze_cost, render_markdown
from .cost_advisor.i18n import normalize_lang

_I18N = {
    "en": {
        "title": "## 💰 Query Cost Advisor\n"
                 "Where does the compute go? Aggregates the query audit "
                 "log into Top-N expensive query templates, per-table scan "
                 "cost, and queries missing a partition filter — with "
                 "expensive-pattern tags from the data-skew rules. "
                 "Recommendations only, nothing executed.",
        "qlog_label": "Audit log path (empty = logs/text2sql_queries.jsonl)",
        "days_label": "Window (days)",
        "top_label": "Top N",
        "dialect_label": "SQL dialect",
        "run_btn": "Analyze",
        "bad_path": "⚠️ File does not exist: ",
    },
    "zh": {
        "title": "## 💰 查询成本顾问\n"
                 "算力花在哪了？聚合查询审计日志，给出 Top 烧钱查询模板、"
                 "按表扫描成本、缺少分区过滤的查询 — 并用数据倾斜规则标注"
                 "昂贵模式。只输出建议，不执行任何语句。",
        "qlog_label": "审计日志路径（留空 = logs/text2sql_queries.jsonl）",
        "days_label": "窗口（天）",
        "top_label": "Top N",
        "dialect_label": "SQL 方言",
        "run_btn": "分析",
        "bad_path": "⚠️ 文件不存在: ",
    },
}

_DIALECTS = ["hive", "spark", "mysql", "postgresql", "clickhouse",
             "doris", "starrocks"]


def _t(lang: str, key: str) -> str:
    return _I18N[normalize_lang(lang)].get(key, key)


def render_cost_advisor_page(app: gr.Blocks) -> None:
    lang0 = "en"
    t = lambda k: _t(lang0, k)  # noqa: E731

    lang_state = gr.State(lang0)

    # marker: body:has(.st-scroll-page) re-enables page scrolling
    gr.HTML('<div class="st-scroll-page" style="display:none"></div>')

    with gr.Column(elem_classes=["st-cost-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])

        with gr.Row():
            with gr.Column(scale=2, elem_classes=["st-cost-side"]):
                qlog_box = gr.Textbox(label=t("qlog_label"), value="")
                days_num = gr.Number(label=t("days_label"), value=30,
                                     precision=0, minimum=1, maximum=365)
                top_num = gr.Number(label=t("top_label"), value=10,
                                    precision=0, minimum=1, maximum=100)
                dialect_dd = gr.Dropdown(
                    choices=_DIALECTS, value="hive",
                    label=t("dialect_label"))
                run_btn = gr.Button(t("run_btn"), variant="primary")

            with gr.Column(scale=5, elem_classes=["st-cost-main"]):
                report_md = gr.Markdown("")

    # ── callbacks ──

    def do_analyze(qlog: str, days: float, top_n: float,
                   dialect: str, lang: str):
        from pathlib import Path
        lang = normalize_lang(lang)
        qlog = (qlog or "").strip() or None
        if qlog and not Path(qlog).is_file():
            return _t(lang, "bad_path") + qlog
        try:
            report = analyze_cost(qlog, days=int(days or 30),
                                  top_n=int(top_n or 10), dialect=dialect)
        except Exception as exc:  # noqa: BLE001 — analysis must never crash the page
            return f"⚠️ {type(exc).__name__}: {exc}"
        return render_markdown(report, lang)

    def switch_lang(choice: str):
        lang = "zh" if choice == "中文" else "en"
        return (
            lang,
            gr.update(value=_t(lang, "title")),
            gr.update(label=_t(lang, "qlog_label")),
            gr.update(label=_t(lang, "days_label")),
            gr.update(label=_t(lang, "top_label")),
            gr.update(label=_t(lang, "dialect_label")),
            gr.update(value=_t(lang, "run_btn")),
        )

    run_btn.click(
        do_analyze,
        inputs=[qlog_box, days_num, top_num, dialect_dd, lang_state],
        outputs=[report_md],
    )

    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, qlog_box, days_num, top_num,
                 dialect_dd, run_btn],
    )
