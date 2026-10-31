"""Render a RepairPlan as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .planner import RepairAction, RepairPlan

__all__ = ["render_markdown"]


def _why(a: RepairAction, lang: str) -> str:
    r = a.rationale
    if a.kind == "dedup":
        return tp(lang, "why_dedup").format(layer=r["layer"],
                                            extra_rows=r["extra_rows"])
    if a.kind == "null_backfill":
        return tp(lang, "why_null").format(null_pct=r["null_pct"])
    if a.kind == "standardize":
        return tp(lang, "why_standardize")
    if a.kind == "numeric_cast":
        ex = ", ".join(f"`{v}`" for v in r.get("examples", []))
        return tp(lang, "why_numeric").format(examples=ex or "-")
    if "buckets" in r:
        buckets = ", ".join(f"{b}:{n}" for b, n in r["buckets"].items())
        return tp(lang, "why_mixed").format(buckets=buckets)
    return tp(lang, "why_format").format(rows=r.get("rows", "-"))


def render_markdown(plan: RepairPlan, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(table=plan.table,
                                          rows=plan.total_rows,
                                          n=len(plan.actions)), ""]
    if plan.actions:
        lines.append(f"### {tp(lang, 'rpt_actions')}")
        rows = [[tp(lang, "kind_" + a.kind), tp(lang, "sev_" + a.severity),
                 f"`{a.column}`" if a.column else "-", _why(a, lang)]
                for a in plan.actions]
        lines += md_table([tp(lang, "col_kind"), tp(lang, "col_sev"),
                           tp(lang, "col_col"), tp(lang, "col_why")], rows)
        lines += ["", f"### {tp(lang, 'rpt_sql')}", "```sql"]
        for a in plan.actions:
            lines.append(a.sql)
            lines.append("")
        lines.append("```")
    else:
        lines.append(tp(lang, "rpt_clean"))
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
