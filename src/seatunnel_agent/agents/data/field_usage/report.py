"""Render a FieldUsageReport as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .analyzer import FieldUsageReport
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(report: FieldUsageReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = report.counts()
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(queries=report.queries_total,
                                          tables=len(report.tables),
                                          medium=counts["medium"],
                                          low=counts["low"],
                                          unresolved=report.unresolved_refs),
             "", f"### {tp(lang, 'rpt_tables')}"]
    rows = [[f"`{t.table}`", str(t.reads),
             str(t.star_reads) if t.star_reads else "-",
             ", ".join(f"`{c}`" for c in t.unused[:6])
             + ("…" if len(t.unused) > 6 else "") if t.unused else "-"]
            for t in report.tables]
    lines += md_table([tp(lang, "col_table"), tp(lang, "col_reads"),
                       tp(lang, "col_star"), tp(lang, "col_unused")], rows)
    if report.top_columns:
        lines += ["", f"### {tp(lang, 'rpt_top')}"]
        lines += md_table([tp(lang, "col_column"), tp(lang, "col_refs")],
                          [[f"`{c}`", str(n)]
                           for c, n in report.top_columns])
    if not report.findings:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code, f"`{f.table}`",
                 tp(lang, f.code).format(detail=f.detail or "-")]
                for f in report.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_table"), tp(lang, "col_issue")],
                          rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
