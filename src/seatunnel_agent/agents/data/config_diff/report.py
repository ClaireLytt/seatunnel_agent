"""Render a ConfigDiffResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .differ import ConfigDiffResult
from .i18n import tp

__all__ = ["render_markdown"]

_TOP_ENTRIES = 40


def render_markdown(result: ConfigDiffResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(left=result.left_keys,
                                          right=result.right_keys,
                                          n=len(result.entries)), ""]
    if result.entries:
        lines.append(f"### {tp(lang, 'rpt_entries')}")
        rows = []
        for e in result.entries[:_TOP_ENTRIES]:
            rows.append([tp(lang, "sev_" + e.severity),
                         tp(lang, "kind_" + e.kind), f"`{e.key}`",
                         f"`{e.old}`" if e.old is not None else "-",
                         f"`{e.new}`" if e.new is not None else "-"])
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_kind"),
                           tp(lang, "col_key"), tp(lang, "col_old"),
                           tp(lang, "col_new")], rows)
    else:
        lines.append(tp(lang, "rpt_identical"))
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
