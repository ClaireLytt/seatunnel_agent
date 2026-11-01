"""Render a CsvDoctorReport as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .doctor import CsvDoctorReport
from .i18n import tp

__all__ = ["render_markdown"]

_PREVIEW_LINES = 12


def render_markdown(report: CsvDoctorReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = report.counts()
    delim = {"\t": "\\t"}.get(report.delimiter, report.delimiter)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(delim=delim, rows=report.rows,
                                          cols=report.columns,
                                          high=counts["high"],
                                          medium=counts["medium"],
                                          low=counts["low"])]
    if report.clean:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code, str(f.count),
                 tp(lang, f.code).format(detail=f.sample or "-")]
                for f in report.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_count"), tp(lang, "col_detail")],
                          rows)
    body = report.fixed_csv.splitlines()
    shown = body[:_PREVIEW_LINES]
    lines += ["", f"### {tp(lang, 'rpt_fixed')}", "```csv",
              *shown]
    if len(body) > _PREVIEW_LINES:
        lines.append(f"... (+{len(body) - _PREVIEW_LINES})")
    lines += ["```", "", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
