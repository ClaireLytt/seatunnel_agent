"""Render a SchemaDiffReport as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import DRIFT_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .differ import SchemaDiffReport
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(report: SchemaDiffReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    verdict = tp(lang, "verdict_ok" if report.compatible else "verdict_bad")
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(flavor=report.flavor,
                                          mode=report.mode.upper(),
                                          old=report.fields_old,
                                          new=report.fields_new,
                                          verdict=verdict)]
    if not report.findings:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[DRIFT_MARK[f.severity], tp(lang, "kind_" + f.kind),
                 f"`{f.fld}`", f"`{f.old}`" if f.old else "-",
                 f"`{f.new}`" if f.new else "-",
                 ", ".join(f.breaks) or "-"]
                for f in report.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_kind"),
                           tp(lang, "col_field"), tp(lang, "col_old"),
                           tp(lang, "col_new"), tp(lang, "col_breaks")],
                          rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
