"""Render a PlanReport as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang

from .analyzer import PlanReport
from .i18n import tp

__all__ = ["render_markdown"]

_SEV_LABEL = {"high": "HIGH", "medium": "MED", "info": "INFO"}


def render_markdown(report: PlanReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = report.counts()
    lines = [f"## {tp(lang, 'rpt_title')}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 joins=sum(report.joins.values()),
                 exchanges=report.exchanges, scans=len(report.scans),
                 **counts) + "**",
             ""]
    if report.findings:
        lines.append(f"### {tp(lang, 'rpt_findings')}")
        lines.append(f"| {tp(lang, 'rpt_col_code')} "
                     f"| {tp(lang, 'rpt_col_severity')} "
                     f"| {tp(lang, 'rpt_col_detail')} "
                     f"| {tp(lang, 'rpt_col_advice')} |")
        lines.append("|---|---|---|---|")
        for f in report.findings:
            lines.append(f"| {f.code} | {_SEV_LABEL[f.severity]} "
                         f"| `{f.detail}` | {tp(lang, f.code)} |")
        lines.append("")
    else:
        lines.append(tp(lang, "rpt_all_ok"))
        lines.append("")
    if report.scans:
        lines.append(f"### {tp(lang, 'rpt_scans')}")
        lines.append(f"| {tp(lang, 'rpt_col_table')} "
                     f"| {tp(lang, 'rpt_col_cols')} "
                     f"| {tp(lang, 'rpt_col_part')} "
                     f"| {tp(lang, 'rpt_col_pushed')} |")
        lines.append("|---|---|---|---|")
        for s in report.scans:
            def mark(value: str | None) -> str:
                if value is None:
                    return tp(lang, "not_stated")
                return (f"**{tp(lang, 'empty_mark')}**" if value == ""
                        else f"`{value[:60]}`")
            lines.append(f"| `{s.table}` | {s.columns} "
                         f"| {mark(s.partition_filters)} "
                         f"| {mark(s.pushed_filters)} |")
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
