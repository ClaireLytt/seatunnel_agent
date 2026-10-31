"""Render a ModelReport as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .reviewer import ModelReport

__all__ = ["render_markdown"]

_ROLE_ORDER = ("dim", "fact", "raw", "other")


def render_markdown(report: ModelReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = report.counts()
    roles = " / ".join(f"{tp(lang, 'role_' + r)} {report.roles[r]}"
                       for r in _ROLE_ORDER if report.roles.get(r))
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(tables=report.tables_total,
                                          roles=roles,
                                          dialect=report.dialect,
                                          high=counts["high"],
                                          medium=counts["medium"],
                                          low=counts["low"])]
    if not report.findings:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        order = {"high": 0, "medium": 1, "low": 2}
        rows = []
        for f in sorted(report.findings,
                        key=lambda f: (order[f.severity], f.code, f.table)):
            issue = tp(lang, f.code).format(detail=f.detail)
            rows.append([SEVERITY_MARK[f.severity], f.code,
                         f"`{f.table}`", issue])
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_table"), tp(lang, "col_issue")],
                          rows)
    if report.warnings:
        lines += ["", f"### {tp(lang, 'rpt_warnings')}"]
        lines += [f"- {w}" for w in report.warnings[:5]]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
