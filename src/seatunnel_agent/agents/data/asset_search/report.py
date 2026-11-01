"""Render a SearchResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .searcher import SearchResult

__all__ = ["render_markdown"]


def render_markdown(result: SearchResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    terms = ", ".join(f"`{t}`" for t in result.terms[:10])
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(query=result.query,
                                          total=result.total_assets,
                                          terms=terms), ""]
    if result.hits:
        lines.append(f"### {tp(lang, 'rpt_hits')}")
        rows = []
        for i, h in enumerate(result.hits, start=1):
            table_cell = (f"`{h.table}`" + (f" — {h.comment}" if h.comment
                                            else ""))
            rows.append([str(i), table_cell, f"{h.score:g}",
                         ", ".join(f"`{c}`" for c in h.matched_columns)
                         or "-",
                         ", ".join(h.reasons) or "-"])
        lines += md_table([tp(lang, "col_rank"), tp(lang, "col_table"),
                           tp(lang, "col_score"), tp(lang, "col_cols"),
                           tp(lang, "col_why")], rows)
    else:
        lines.append(tp(lang, "rpt_no_hits"))
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
