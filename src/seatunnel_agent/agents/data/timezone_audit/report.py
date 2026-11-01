"""Render a TimezoneAudit as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .auditor import TimezoneAudit
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(audit: TimezoneAudit, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = audit.counts()
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(cols=len(audit.columns),
                                          high=counts["high"],
                                          medium=counts["medium"]), "",
             f"### {tp(lang, 'rpt_columns')}"]
    rows = [[f"`{c.name}`",
             ", ".join(f"{k}x{v}" for k, v in sorted(c.kinds.items())),
             ", ".join(f"{k}x{v}" for k, v in sorted(c.offsets.items()))
             or "-",
             str(c.sentinel) if c.sentinel else "-",
             f"{c.hour_modes[0]:02d}h/{c.hour_modes[1]:02d}h"
             if c.hour_modes else "-"]
            for c in audit.columns]
    lines += md_table([tp(lang, "col_name"), tp(lang, "col_kinds"),
                       tp(lang, "col_offsets"), tp(lang, "col_sentinel"),
                       tp(lang, "col_modes")], rows)
    if not audit.findings:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code, f"`{f.column}`",
                 tp(lang, f.code).format(detail=f.detail or "-")]
                for f in audit.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_name"), tp(lang, "col_issue")],
                          rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
