# -*- coding: utf-8 -*-
"""Render a CostReport as markdown (zh/en) or a plain dict."""

from __future__ import annotations

from typing import Any

from .analyzer import DEFAULT_PARTITION_COLS, CostReport
from .i18n import COST_I18N, normalize_lang

_TPL_MAX = 80


def _short(sql: str) -> str:
    sql = " ".join(sql.split())
    return sql if len(sql) <= _TPL_MAX else sql[:_TPL_MAX - 1] + "…"


def render_markdown(report: CostReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    t = COST_I18N[lang]
    lines: list[str] = [f"# {t['rpt_title']}", ""]
    lines.append(t["rpt_window"].format(
        days=report.days, records=report.record_count,
        success=report.success_count,
        total_s=round(report.total_ms / 1000, 1)))
    lines.append("")
    if not report.success_count:
        lines += [t["rpt_empty"], "", t["rpt_disclaimer"]]
        return "\n".join(lines)

    lines.append(f"## {t['rpt_top']}")
    lines.append(t["rpt_top_cols"])
    lines.append("|---|---|---|---|---|---|---|---|")
    for i, q in enumerate(report.top_queries, 1):
        patterns = ", ".join(q.skew_categories) or t["rpt_none"]
        lines.append(
            f"| {i} | {q.total_ms} | {q.runs} | {q.avg_ms} | {q.max_ms} "
            f"| {q.total_rows} | {', '.join(q.tables) or '-'} "
            f"| {patterns} |")
        lines.append(f"| | `{_short(q.template)}` |||||||")
    lines.append("")

    lines.append(f"## {t['rpt_tables']}")
    lines.append(t["rpt_tables_cols"])
    lines.append("|---|---|---|")
    for tc in report.table_costs:
        lines.append(f"| {tc.table} | {tc.queries} | {tc.total_ms} |")
    lines.append("")

    lines.append(f"## {t['rpt_nofilter']}")
    if report.no_partition_filter:
        for q in report.no_partition_filter:
            lines.append(f"- `{_short(q.template)}` — "
                         f"{q.runs}x · {q.total_ms} ms")
    else:
        lines.append(t["rpt_none"])
    lines.append("")
    lines.append(t["rpt_nofilter_note"].format(
        cols=", ".join(DEFAULT_PARTITION_COLS)))
    lines += ["", t["rpt_disclaimer"]]
    return "\n".join(lines)


def report_to_dict(report: CostReport, lang: str = "zh") -> dict[str, Any]:
    data = report.to_dict()
    data["lang"] = normalize_lang(lang)
    return data
