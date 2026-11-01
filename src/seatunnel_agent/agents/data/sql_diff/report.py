"""Render a SqlDiffReport as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import DRIFT_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .differ import SqlDiffReport
from .i18n import tp

__all__ = ["render_markdown"]

_CLIP = 60


def _clip(s: str) -> str:
    s = s or "-"
    return s if len(s) <= _CLIP else s[:_CLIP - 1] + "…"


def render_markdown(report: SqlDiffReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = report.counts()
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(old=report.statements_old,
                                          new=report.statements_new,
                                          dialect=report.dialect,
                                          breaking=counts["breaking"],
                                          risk=counts["risk"],
                                          info=counts["info"])]
    if report.identical:
        lines += ["", tp(lang, "rpt_identical")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        order = {"breaking": 0, "risk": 1, "info": 2}
        rows = []
        for f in sorted(report.findings,
                        key=lambda f: (order[f.severity], f.target)):
            what = tp(lang, "kind_" + f.kind)
            if f.subject:
                what += f" · `{f.subject}`"
            rows.append([DRIFT_MARK[f.severity], f"`{f.target}`", what,
                         f"`{_clip(f.old)}`", f"`{_clip(f.new)}`"])
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_target"),
                           tp(lang, "col_what"), tp(lang, "col_old"),
                           tp(lang, "col_new")], rows)
    if report.warnings:
        lines += ["", f"### {tp(lang, 'rpt_warnings')}"]
        lines += [f"- {w}" for w in report.warnings[:5]]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
