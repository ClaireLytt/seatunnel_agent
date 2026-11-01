"""Render a CompactPlan as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .planner import CompactPlan

__all__ = ["render_markdown"]

_SHOW = 10
_SQL = 3


def render_markdown(plan: CompactPlan, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = plan.counts()
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(parts=plan.partitions,
                                          files=plan.files_total,
                                          freed=plan.files_freed,
                                          high=counts["high"],
                                          medium=counts["medium"])]
    if not plan.candidates:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_cands')}"]
        rows = [[f"`{c.table}`", f"`{c.partition}`", str(c.file_count),
                 f"{c.avg_mb:g}", str(c.files_after),
                 str(c.files_freed)]
                for c in plan.candidates[:_SHOW]]
        lines += md_table([tp(lang, "col_table"),
                           tp(lang, "col_partition"),
                           tp(lang, "col_files"), tp(lang, "col_avg"),
                           tp(lang, "col_after"), tp(lang, "col_freed")],
                          rows)
        shown = plan.candidates[:_SQL]
        lines += ["", f"### {tp(lang, 'rpt_sql').format(n=len(shown))}",
                  "```sql"]
        for c in shown:
            lines.append(f"ALTER TABLE {c.table} PARTITION ({c.partition})"
                         " CONCATENATE;")
            lines.append(f"-- or: INSERT OVERWRITE TABLE {c.table} "
                         f"PARTITION ({c.partition}) SELECT ... ;")
        lines.append("```")
    if plan.findings:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code, f"`{f.table}`",
                 tp(lang, f.code).format(detail=f.detail or "-",
                                         value=f.value)]
                for f in plan.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_table"), tp(lang, "col_issue")],
                          rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
