"""Render a WatermarkPlan as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .planner import WatermarkPlan

__all__ = ["render_markdown"]


def render_markdown(plan: WatermarkPlan, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(events=plan.events,
                                          ooo=plan.out_of_order_share,
                                          p50=plan.p50_s, p95=plan.p95_s,
                                          p99=plan.p99_s, max=plan.max_s),
             "",
             tp(lang, "rpt_reco").format(bound=plan.bound_s,
                                         residual=plan.residual_share),
             "", f"### {tp(lang, 'rpt_snippets')}", "```sql",
             plan.sql_clause, "```", "```java", plan.java_snippet, "```"]
    if not plan.findings:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code,
                 tp(lang, f.code).format(value=f.value)]
                for f in plan.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_issue")], rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
