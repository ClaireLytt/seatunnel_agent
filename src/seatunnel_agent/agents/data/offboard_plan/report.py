"""Render an OffboardPlan as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .planner import OffboardPlan

__all__ = ["render_markdown"]


def render_markdown(plan: OffboardPlan, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(table=plan.table,
                                          grace=plan.grace_days,
                                          steps=len(plan.steps))]
    if plan.blocked:
        consumers = ", ".join(f"`{t}` (+{d})"
                              for t, d in sorted(plan.downstream.items()))
        lines += ["", tp(lang, "rpt_blocked").format(
            n=len(plan.downstream), consumers=consumers)]
    else:
        lines += ["", tp(lang, "rpt_clear")]
    lines += ["", f"### {tp(lang, 'rpt_steps')}"]
    rows = [[tp(lang, "phase_" + s.phase), tp(lang, "act_" + s.action),
             tp(lang, "state_safe" if s.safe else "state_unsafe"),
             s.detail or "-"]
            for s in plan.steps]
    lines += md_table([tp(lang, "col_phase"), tp(lang, "col_action"),
                       tp(lang, "col_state"), tp(lang, "col_detail")],
                      rows)
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
