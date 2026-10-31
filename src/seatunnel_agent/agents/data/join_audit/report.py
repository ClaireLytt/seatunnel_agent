"""Render a JoinAuditReport as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .auditor import JoinAuditReport
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(report: JoinAuditReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    keys = ", ".join(a if a == b else f"{a}={b}" for a, b in report.keys)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(
                 lrows=report.left_rows, rrows=report.right_rows,
                 keys=keys, lmatch=report.left_match_rate,
                 rmatch=report.right_match_rate,
                 joined=report.joined_rows,
                 explosion=round(report.explosion, 2))]
    if not report.findings:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code,
                 tp(lang, "side_" + f.side),
                 tp(lang, f.code).format(detail=f.detail or "-",
                                         value=(round(f.value, 2)
                                                if f.code == "JA001"
                                                else f.value))]
                for f in report.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_side"), tp(lang, "col_issue")],
                          rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
