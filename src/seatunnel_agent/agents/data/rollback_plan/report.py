"""Render a RollbackPlan as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .planner import RollbackPlan

__all__ = ["render_markdown"]


def render_markdown(plan: RollbackPlan, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    est = (tp(lang, "rpt_est").format(m=plan.estimated_min)
           if plan.estimated_min is not None else "")
    parts = ", ".join(f"`{p}`" for p in plan.partitions) or "-"
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(table=plan.table, parts=parts,
                                          mode=plan.mode,
                                          levels=plan.levels,
                                          touched=len(plan.touched),
                                          est=est), "",
             f"### {tp(lang, 'rpt_steps')}"]
    rows = [[str(s.level), tp(lang, "action_" + s.action), f"`{s.table}`"]
            for s in plan.steps]
    lines += md_table([tp(lang, "col_level"), tp(lang, "col_action"),
                       tp(lang, "col_table")], rows)
    lines += ["", f"### {tp(lang, 'rpt_sql')}", "```sql"]
    for s in plan.steps:
        lines.append(s.sql)
        lines.append("")
    lines.append("```")
    if plan.warnings:
        lines += ["", f"### {tp(lang, 'rpt_warnings')}"]
        lines += [f"- {w}" for w in plan.warnings[:5]]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
