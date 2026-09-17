"""Gradio page for the SQL Code Review agent.

Rendered inside the multipage app built by ``ui.create_ui`` via
``app.route("SQL Review", "/sqlreview")``.  Static mode is pure local
linting; LLM mode runs the full review agent.
"""

from __future__ import annotations

import time

import gradio as gr

from .config import load_settings
from .sql_review.agent import SQLReviewAgent, static_review_report
from .sql_review.fixer import generate_fix
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


def _err_md(exc: Exception) -> str:
    return f"❌ **审查失败**：{exc}"


def render_sql_review_page(app: gr.Blocks) -> None:
    gr.Markdown("## 🔍 SQL Code Review · SQL 代码审查\n"
                "静态规则 + LLM 语义审查，支持 Hive / Spark / Flink / MaxCompute。"
                "纯静态分析，不执行 SQL。")

    with gr.Row():
        with gr.Column(scale=3):
            sql_box = gr.Textbox(
                label="SQL", lines=12, placeholder="粘贴要审查的 SQL……",
                value=_EXAMPLE_SQL,
            )
            with gr.Row():
                dialect_dd = gr.Dropdown(
                    choices=_DIALECT_CHOICES, value="hive", label="SQL 方言",
                )
                mode_radio = gr.Radio(
                    choices=[("静态审查（快速，无需 LLM）", "static"),
                             ("LLM 深度审查", "agent")],
                    value="static", label="审查模式",
                )
            with gr.Accordion("表结构 DDL（可选，用于 schema 校验）", open=False):
                ddl_box = gr.Textbox(
                    label="CREATE TABLE 语句", lines=6,
                    placeholder="CREATE TABLE ods.user_log (user_id BIGINT, dt STRING) ...",
                )
            with gr.Row():
                review_btn = gr.Button("开始审查", variant="primary")
                fix_btn = gr.Button("生成修复 SQL（LLM）")
        with gr.Column(scale=4):
            report_md = gr.Markdown("*审查报告将显示在这里*")
            fixed_sql_box = gr.Code(label="修复后 SQL", language="sql", visible=False)

    report_state = gr.State("")

    def _build_store(ddl: str) -> SchemaStore | None:
        ddl = (ddl or "").strip()
        if not ddl:
            return None
        from .text2sql.schema import parse_ddl
        tables = parse_ddl(ddl)
        return SchemaStore(tables) if tables else None

    def do_review(sql: str, dialect: str, mode: str, ddl: str):
        sql = (sql or "").strip()
        if not sql:
            return "请先输入 SQL。", "", gr.update(visible=False)
        dialect = normalize_dialect(dialect)
        start = time.time()
        try:
            store = _build_store(ddl)
            if mode == "static":
                rep = static_review_report(sql, dialect, store=store)
                report = render_report(rep)
                findings, stats = rep.findings, rep.stats()
            else:
                settings = load_settings()
                agent = SQLReviewAgent(settings, dialect=dialect, store=store)
                report = agent.review(sql)
                findings, stats = [], {}
                if agent.runtime and agent.runtime.report:
                    findings = agent.runtime.report.findings
                    stats = agent.runtime.report.stats()
        except Exception as exc:  # noqa: BLE001 — surface any failure in the UI
            return _err_md(exc), "", gr.update(visible=False)
        ReviewLogger().log(
            sql=sql, dialect=dialect, mode=mode, findings=findings,
            stats=stats, source="ui",
            elapsed_ms=int((time.time() - start) * 1000),
        )
        return report, report, gr.update(visible=False)

    def do_fix(sql: str, dialect: str, report: str):
        sql = (sql or "").strip()
        if not sql or not report:
            return gr.update(value="-- 请先完成一次审查", visible=True)
        try:
            settings = load_settings()
            fixed = generate_fix(settings, sql, normalize_dialect(dialect), report)
        except Exception as exc:  # noqa: BLE001
            return gr.update(value=f"-- 修复失败: {exc}", visible=True)
        return gr.update(value=fixed, visible=True)

    review_btn.click(
        do_review,
        inputs=[sql_box, dialect_dd, mode_radio, ddl_box],
        outputs=[report_md, report_state, fixed_sql_box],
    )
    fix_btn.click(
        do_fix,
        inputs=[sql_box, dialect_dd, report_state],
        outputs=[fixed_sql_box],
    )

    with gr.Accordion("📈 审查历史统计", open=False):
        stats_md = gr.Markdown("*点击刷新查看*")
        trend_plot = gr.Plot(visible=False)
        refresh_btn = gr.Button("刷新统计", size="sm")

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

        def load_stats():
            logger = ReviewLogger()
            s = logger.summarize()
            if not s["reviews"]:
                return "暂无审查记录。", gr.update(visible=False)
            lines = [f"- 审查次数：{s['reviews']}",
                     f"- 发现问题总数：{s['findings']}"]
            sev_names = {"critical": "🔴 严重", "risk": "🟡 风险", "suggestion": "🟢 建议"}
            for sev, cnt in s["severities"].items():
                lines.append(f"- {sev_names.get(sev, sev)}：{cnt}")
            if s["top_categories"]:
                lines.append("\n**高频问题类别**：")
                for item in s["top_categories"][:5]:
                    lines.append(f"- {item['label']}（{item['count']} 次）")
            try:
                fig = _trend_figure(logger.recent(500))
            except Exception:  # noqa: BLE001 — the chart is optional
                fig = None
            plot_update = (gr.update(value=fig, visible=True) if fig is not None
                           else gr.update(visible=False))
            return "\n".join(lines), plot_update

        refresh_btn.click(load_stats, outputs=[stats_md, trend_plot])
