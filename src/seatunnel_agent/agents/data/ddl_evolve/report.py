"""Render an EvolvePlan as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .evolver import EvolvePlan
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(plan: EvolvePlan, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(total=len(plan.steps),
                                          safe=plan.safe_steps,
                                          unsafe=plan.unsafe_steps,
                                          dialect=plan.dialect)]
    if not plan.steps:
        lines += ["", tp(lang, "rpt_identical")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_steps')}"]
        rows = [["●" if not s.safe else "○",
                 tp(lang, "kind_" + s.kind), f"`{s.table}`",
                 s.note or "-"]
                for s in plan.steps]
        lines += md_table([tp(lang, "col_state"), tp(lang, "col_kind"),
                           tp(lang, "col_table"), tp(lang, "col_note")],
                          rows)
        lines += ["", f"### {tp(lang, 'rpt_script')}", "```sql",
                  plan.to_script().rstrip(), "```"]
    if plan.warnings:
        lines += ["", f"### {tp(lang, 'rpt_warnings')}"]
        lines += [f"- {w}" for w in plan.warnings[:5]]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
