"""Render a CoverageMap as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .mapper import CoverageMap

__all__ = ["render_markdown"]


def render_markdown(cmap: CoverageMap, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = cmap.counts()
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(covered=cmap.covered,
                                          total=len(cmap.tables),
                                          share=cmap.coverage_share,
                                          high=counts["high"],
                                          medium=counts["medium"]), "",
             f"### {tp(lang, 'rpt_tables')}"]
    yes = tp(lang, "yes")
    rows = [[f"`{t.table}`",
             str(t.checks["row_count"]) if t.checks["row_count"] else "-",
             str(t.checks["null_rate"]) if t.checks["null_rate"] else "-",
             str(t.checks["unique"]) if t.checks["unique"] else "-",
             str(t.checks["enum_domain"]) if t.checks["enum_domain"]
             else "-",
             yes if t.contract else "-"]
            for t in cmap.tables]
    lines += md_table([tp(lang, "col_table"), tp(lang, "col_rowcount"),
                       tp(lang, "col_nullrate"), tp(lang, "col_unique"),
                       tp(lang, "col_enum"), tp(lang, "col_contract")],
                      rows)
    if not cmap.findings:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code, f"`{f.table}`",
                 tp(lang, f.code).format(detail=f.detail or "-")]
                for f in cmap.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_table"), tp(lang, "col_issue")],
                          rows)
    unguarded = [f.table for f in cmap.findings if f.code == "CM001"]
    if unguarded:
        lines += ["", f"### {tp(lang, 'rpt_cmds')}", "```bash"]
        for table in unguarded:
            lines.append(
                f"seatunnel-agent dqrulegen -f <sample.csv> -t {table}"
                f"  # + contractgen -f <ddl.sql> -t {table}")
        lines.append("```")
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
