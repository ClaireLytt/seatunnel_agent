"""Gradio page for the SQL Code Review agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("SQL Review", "/sqlreview")``.  Static mode is pure local
linting; LLM mode runs the full review agent.  The page is bilingual
(EN/ZH) following the same switch pattern as the Data Comparison page.
"""

from __future__ import annotations

import time

import gradio as gr

from .config import load_settings
from .sql_review.agent import SQLReviewAgent, static_review_report
from .sql_review.fixer import generate_fix
from .sql_review.i18n import catalog_label, sr
from .sql_review.linter import normalize_dialect
from .sql_review.report import render_report
from .sql_review.rlog import ReviewLogger
from .text2sql.schema import SchemaStore

_DIALECT_CHOICES = [("Hive SQL", "hive"), ("Spark SQL", "spark"),
                    ("Flink SQL", "flink"), ("MaxCompute SQL", "maxcompute")]

_EXAMPLE_SQL = """\
INSERT OVERWRITE TABLE dw.ads_user_stat
SELECT *
FROM ods.user_log a
JOIN dim.user_info b ON a.user_id = b.user_id
ORDER BY a.user_id"""

_DEFAULT_LANG = "en"


def _mode_choices(lang: str) -> list[tuple[str, str]]:
    return [(sr(lang, "sr_mode_static"), "static"),
            (sr(lang, "sr_mode_llm"), "agent")]


def _err_md(exc: Exception, lang: str) -> str:
    sep = ": " if lang == "en" else "："
    return f"{sr(lang, 'sr_review_failed')}{sep}{exc}"


def render_sql_review_page(app: gr.Blocks) -> None:
    t0 = lambda k: sr(_DEFAULT_LANG, k)  # noqa: E731 — initial labels

    with gr.Row():
        title_md = gr.Markdown(f"{t0('sr_title')}\n{t0('sr_subtitle')}")
        lang_dd = gr.Dropdown(
            choices=["English", "中文"], value="English",
            show_label=False, container=False, min_width=140, scale=0,
        )
    lang_state = gr.State(_DEFAULT_LANG)

    with gr.Row():
        with gr.Column(scale=3):
            sql_box = gr.Textbox(
                label="SQL", lines=12, placeholder=t0("sr_sql_placeholder"),
                value=_EXAMPLE_SQL,
            )
            with gr.Row():
                dialect_dd = gr.Dropdown(
                    choices=_DIALECT_CHOICES, value="hive", label=t0("sr_dialect"),
                )
                mode_radio = gr.Radio(
                    choices=_mode_choices(_DEFAULT_LANG),
                    value="static", label=t0("sr_mode"),
                )
            with gr.Accordion(t0("sr_ddl_accordion"), open=False) as ddl_acc:
                ddl_box = gr.Textbox(
                    label=t0("sr_ddl_label"), lines=6,
                    placeholder="CREATE TABLE ods.user_log (user_id BIGINT, dt STRING) ...",
                )
            with gr.Row():
                review_btn = gr.Button(t0("sr_review_btn"), variant="primary")
                fix_btn = gr.Button(t0("sr_fix_btn"))
        with gr.Column(scale=4):
            report_md = gr.Markdown(t0("sr_report_placeholder"))
            fixed_sql_box = gr.Code(label=t0("sr_fixed_sql"), language="sql",
                                    visible=False)

    report_state = gr.State("")

    def _build_store(ddl: str) -> SchemaStore | None:
        ddl = (ddl or "").strip()
        if not ddl:
            return None
        from .text2sql.schema import parse_ddl
        tables = parse_ddl(ddl)
        return SchemaStore(tables) if tables else None

    def do_review(sql: str, dialect: str, mode: str, ddl: str, lang: str):
        sql = (sql or "").strip()
        if not sql:
            return sr(lang, "sr_input_sql_first"), "", gr.update(visible=False)
        dialect = normalize_dialect(dialect)
        start = time.time()
        try:
            store = _build_store(ddl)
            if mode == "static":
                rep = static_review_report(sql, dialect, store=store)
                report = render_report(rep, lang=lang)
                findings, stats = rep.findings, rep.stats()
            else:
                settings = load_settings()
                agent = SQLReviewAgent(settings, dialect=dialect, store=store,
                                       lang=lang)
                report = agent.review(sql)
                findings, stats = [], {}
                if agent.runtime and agent.runtime.report:
                    findings = agent.runtime.report.findings
                    stats = agent.runtime.report.stats()
        except Exception as exc:  # noqa: BLE001 — surface any failure in the UI
            return _err_md(exc, lang), "", gr.update(visible=False)
        ReviewLogger().log(
            sql=sql, dialect=dialect, mode=mode, findings=findings,
            stats=stats, source="ui",
            elapsed_ms=int((time.time() - start) * 1000),
        )
        return report, report, gr.update(visible=False)

    def do_fix(sql: str, dialect: str, report: str, lang: str):
        sql = (sql or "").strip()
        if not sql or not report:
            return gr.update(value=sr(lang, "sr_fix_need_review"), visible=True)
        try:
            settings = load_settings()
            fixed = generate_fix(settings, sql, normalize_dialect(dialect),
                                 report, lang=lang)
        except Exception as exc:  # noqa: BLE001
            sep = ": " if lang == "en" else "："
            return gr.update(value=f"{sr(lang, 'sr_fix_failed')}{sep}{exc}",
                             visible=True)
        return gr.update(value=fixed, visible=True)

    review_btn.click(
        do_review,
        inputs=[sql_box, dialect_dd, mode_radio, ddl_box, lang_state],
        outputs=[report_md, report_state, fixed_sql_box],
    )
    fix_btn.click(
        do_fix,
        inputs=[sql_box, dialect_dd, report_state, lang_state],
        outputs=[fixed_sql_box],
    )

    with gr.Accordion(t0("sr_stats_accordion"), open=False) as stats_acc:
        stats_md = gr.Markdown(t0("sr_stats_placeholder"))
        trend_plot = gr.Plot(visible=False)
        refresh_btn = gr.Button(t0("sr_refresh"), size="sm")

        def _trend_figure(records: list[dict]):
            by_day: dict[str, dict[str, int]] = {}
            for r in records:
                day = (r.get("timestamp") or "")[:10]
                if not day:
                    continue
                bucket = by_day.setdefault(
                    day, {"critical": 0, "risk": 0, "suggestion": 0})
                for sev, cnt in (r.get("severities") or {}).items():
                    if sev in bucket:
                        bucket[sev] += cnt
            if not by_day:
                return None
            # plain Figure (not pyplot) — no global figure registry to leak
            # into on repeated refreshes
            from matplotlib.figure import Figure
            days = sorted(by_day)[-14:]
            crit = [by_day[d]["critical"] for d in days]
            risk = [by_day[d]["risk"] for d in days]
            sugg = [by_day[d]["suggestion"] for d in days]
            fig = Figure(figsize=(7, 3))
            ax = fig.subplots()
            ax.bar(days, crit, color="#dc2626", label="critical")
            ax.bar(days, risk, bottom=crit, color="#f59e0b", label="risk")
            bottom2 = [c + r for c, r in zip(crit, risk)]
            ax.bar(days, sugg, bottom=bottom2, color="#10b981", label="suggestion")
            ax.set_ylabel("findings")
            ax.set_title("Findings per day (last 14 days)")
            ax.legend(fontsize=8)
            for lbl in ax.get_xticklabels():
                lbl.set_rotation(30)
                lbl.set_ha("right")
                lbl.set_fontsize(8)
            fig.tight_layout()
            return fig

        def load_stats(lang: str):
            sep = ": " if lang == "en" else "："
            logger = ReviewLogger()
            s = logger.summarize()
            if not s["reviews"]:
                return sr(lang, "sr_no_records"), gr.update(visible=False)
            lines = [f"- {sr(lang, 'sr_stat_reviews')}{sep}{s['reviews']}",
                     f"- {sr(lang, 'sr_stat_findings')}{sep}{s['findings']}"]
            sev_names = {"critical": sr(lang, "sr_sev_critical"),
                         "risk": sr(lang, "sr_sev_risk"),
                         "suggestion": sr(lang, "sr_sev_suggestion")}
            for sev, cnt in s["severities"].items():
                lines.append(f"- {sev_names.get(sev, sev)}{sep}{cnt}")
            if s["top_categories"]:
                lines.append(f"\n{sr(lang, 'sr_top_categories')}")
                for item in s["top_categories"][:5]:
                    label = catalog_label(item.get("category", ""), lang) \
                        if item.get("category") else item["label"]
                    if lang == "en":
                        lines.append(f"- {label} ({item['count']})")
                    else:
                        lines.append(f"- {label}（{item['count']} 次）")
            try:
                fig = _trend_figure(logger.recent(500))
            except Exception:  # noqa: BLE001 — the chart is optional
                fig = None
            plot_update = (gr.update(value=fig, visible=True) if fig is not None
                           else gr.update(visible=False))
            return "\n".join(lines), plot_update

        refresh_btn.click(load_stats, inputs=[lang_state],
                          outputs=[stats_md, trend_plot])

    # Language switch — update all component labels/text. The returned tuple
    # must stay positionally aligned with the outputs list below.
    def _switch_lang(choice: str):
        lg = "zh" if choice == "中文" else "en"
        t = lambda k: sr(lg, k)  # noqa: E731
        return (
            lg,                                                     # lang_state
            f"{t('sr_title')}\n{t('sr_subtitle')}",                 # title_md
            gr.update(placeholder=t("sr_sql_placeholder")),         # sql_box
            gr.update(label=t("sr_dialect")),                       # dialect_dd
            gr.update(label=t("sr_mode"), choices=_mode_choices(lg)),  # mode_radio
            gr.update(label=t("sr_ddl_accordion")),                 # ddl_acc
            gr.update(label=t("sr_ddl_label")),                     # ddl_box
            gr.update(value=t("sr_review_btn")),                    # review_btn
            gr.update(value=t("sr_fix_btn")),                       # fix_btn
            gr.update(label=t("sr_fixed_sql")),                     # fixed_sql_box
            gr.update(label=t("sr_stats_accordion")),               # stats_acc
            gr.update(value=t("sr_refresh")),                       # refresh_btn
        )

    lang_dd.change(
        _switch_lang,
        inputs=[lang_dd],
        outputs=[
            lang_state,
            title_md,
            sql_box,
            dialect_dd,
            mode_radio,
            ddl_acc,
            ddl_box,
            review_btn,
            fix_btn,
            fixed_sql_box,
            stats_acc,
            refresh_btn,
        ],
    )
