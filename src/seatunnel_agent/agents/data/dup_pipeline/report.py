"""Render a DupReport as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .detector import DupReport
from .i18n import tp

__all__ = ["render_markdown"]


def _issue(f, lang: str) -> str:
    if f.code == "DP001":
        key = "DP001_expr" if f.severity == "high" else "DP001_input"
        return tp(lang, key).format(detail=f.detail, overlap=f.overlap)
    if f.code == "DP003":
        return tp(lang, "DP003").format(detail=f.detail, n=len(f.tables))
    return tp(lang, f.code).format(detail=f.detail)


def render_markdown(report: DupReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = report.counts()
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(targets=report.targets_total,
                                          sources=report.sources_total,
                                          dialect=report.dialect,
                                          high=counts["high"],
                                          medium=counts["medium"],
                                          low=counts["low"])]
    if not report.findings:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code,
                 ", ".join(f"`{t}`" for t in f.tables[:4])
                 + ("…" if len(f.tables) > 4 else ""),
                 _issue(f, lang)]
                for f in report.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_tables"), tp(lang, "col_issue")],
                          rows)
    if report.warnings:
        lines += ["", f"### {tp(lang, 'rpt_warnings')}"]
        lines += [f"- {w}" for w in report.warnings[:5]]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
