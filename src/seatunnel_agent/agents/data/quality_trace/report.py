"""Render a TraceResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .tracer import _MAX_DEPTH, TraceResult

__all__ = ["render_markdown"]

_VERIFY_TOP = 3


def render_markdown(result: TraceResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    col = (tp(lang, "rpt_col_suffix").format(col=result.column)
           if result.column else "")
    event_key = "rpt_event" if result.symptom else "rpt_event_nosym"
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, event_key).format(table=result.table, col=col,
                                        symptom=result.symptom), "",
             tp(lang, "rpt_scope").format(n=result.upstream_tables,
                                          depth=_MAX_DEPTH), ""]
    if result.suspects:
        lines.append(f"### {tp(lang, 'rpt_suspects')}")
        rows = []
        for i, s in enumerate(result.suspects, start=1):
            rows.append([str(i), f"`{s.table}`", str(s.distance),
                         f"{s.score:g}",
                         ", ".join(f"`{c}`" for c in s.column_hits) or "-",
                         "; ".join(f"`{e}`" for e in s.expressions) or "-"])
        lines += md_table([tp(lang, "col_rank"), tp(lang, "col_table"),
                           tp(lang, "col_dist"), tp(lang, "col_score"),
                           tp(lang, "col_hits"), tp(lang, "col_expr")],
                          rows)
        lines += ["", f"### {tp(lang, 'rpt_verify')}", "```sql"]
        for s in result.suspects[:_VERIFY_TOP]:
            lines.append(f"-- {s.table}")
            lines.append(s.verify_sql)
        lines.append("```")
    else:
        lines.append(tp(lang, "rpt_no_suspects"))
    if result.warnings:
        lines += ["", f"### {tp(lang, 'rpt_warnings')}"]
        lines += [f"- {w}" for w in result.warnings[:5]]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
