"""Render a PartitionPlan as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .planner import PartitionPlan

__all__ = ["render_markdown"]


def render_markdown(plan: PartitionPlan, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(cands=len(plan.candidates),
                                          queries=plan.queries_total),
             "", f"### {tp(lang, 'rpt_reco')}"]
    if plan.partition_by:
        lines += ["```sql", plan.partition_by]
        if plan.cluster_by:
            lines.append(plan.cluster_by)
        lines.append("```")
    else:
        lines.append(tp(lang, "rpt_no_reco"))
        if plan.cluster_by:
            lines += ["```sql", plan.cluster_by, "```"]
    lines += ["", f"### {tp(lang, 'rpt_cands')}"]
    rows = [[f"`{c.column}`", c.kind, str(c.distinct),
             str(c.filter_hits), f"{c.score:.2f}",
             f"{tp(lang, 'v_' + c.verdict)} — "
             f"{tp(lang, 'r_' + c.reason)}"]
            for c in plan.candidates]
    lines += md_table([tp(lang, "col_column"), tp(lang, "col_kind"),
                       tp(lang, "col_distinct"), tp(lang, "col_hits"),
                       tp(lang, "col_score"), tp(lang, "col_verdict")],
                      rows)
    if plan.findings:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code,
                 tp(lang, f.code).format(detail=f.detail or "-")]
                for f in plan.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_issue")], rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
