"""Render a DupResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .detector import DupResult
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(result: DupResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(
                 total=result.total_rows, row=result.row_dup_rows,
                 pk=result.pk_dup_rows, biz=result.biz_dup_rows), "",
             tp(lang, "rpt_keys").format(
                 pk=", ".join(f"`{c}`" for c in result.pk_columns) or "(none)",
                 biz=", ".join(f"`{c}`" for c in result.biz_columns)
                 or "(none)"), ""]
    if result.groups:
        lines.append(f"### {tp(lang, 'rpt_groups')}".format(
            n=len(result.groups)))
        rows = []
        for g in result.groups:
            rows.append([tp(lang, "layer_" + g.layer), f"`{g.key}`",
                         str(g.count), f"{g.first_row} → {g.last_row}",
                         ", ".join(f"`{c}`" for c in g.diff_columns) or "-"])
        lines += md_table([tp(lang, "col_layer"), tp(lang, "col_key"),
                           tp(lang, "col_count"), tp(lang, "col_span"),
                           tp(lang, "col_diff")], rows)
        lines.append("")
        if any(g.layer == "row" for g in result.groups):
            lines.append(tp(lang, "rpt_hint_row"))
        if any(g.layer in ("pk", "biz") for g in result.groups):
            lines.append(tp(lang, "rpt_hint_keys"))
    else:
        lines.append(tp(lang, "rpt_clean"))
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
