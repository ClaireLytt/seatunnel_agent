"""Render a RetentionReport as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .advisor import RetentionReport
from .i18n import tp

__all__ = ["render_markdown"]


def _clip(parts: list[str]) -> str:
    if not parts:
        return "-"
    shown = ", ".join(f"`{p}`" for p in parts[:3])
    return shown + (f" +{len(parts) - 3}" if len(parts) > 3 else "")


def render_markdown(report: RetentionReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = report.counts()
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(today=report.today,
                                          tables=len(report.tables),
                                          total=round(report.total_gb, 1),
                                          reclaim=round(
                                              report.reclaimable_gb, 1),
                                          high=counts["high"],
                                          medium=counts["medium"],
                                          low=counts["low"]), "",
             f"### {tp(lang, 'rpt_tables')}"]
    d = tp(lang, "days_suffix")
    rows = [[f"`{t.table}`", str(t.partitions),
             f"{t.total_gb:g}", f"{t.ttl_days}{d}",
             f"{t.cold_gb:g}" if t.cold_gb else "-",
             _clip(t.archive), _clip(t.purge)]
            for t in report.tables]
    lines += md_table([tp(lang, "col_table"), tp(lang, "col_parts"),
                       tp(lang, "col_total"), tp(lang, "col_ttl"),
                       tp(lang, "col_cold"), tp(lang, "col_archive"),
                       tp(lang, "col_purge")], rows)
    if not report.findings:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code, f"`{f.table}`",
                 tp(lang, f.code).format(value=f.value)]
                for f in report.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_table"), tp(lang, "col_issue")],
                          rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
