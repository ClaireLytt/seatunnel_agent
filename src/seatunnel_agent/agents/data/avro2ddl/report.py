"""Render a DdlDraft as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .converter import DdlDraft
from .i18n import tp

__all__ = ["render_markdown"]


def _note(c, lang: str) -> str:
    if c.note.startswith("enum:"):
        return tp(lang, "note_enum")
    return tp(lang, "note_" + c.note)


def render_markdown(draft: DdlDraft, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(flavor=draft.flavor,
                                          dialect=draft.dialect,
                                          table=draft.table,
                                          cols=len(draft.columns),
                                          lossy=draft.lossy), "",
             f"### {tp(lang, 'rpt_columns')}"]
    rows = [[f"`{c.name}`", f"`{c.source_type}`", f"`{c.ddl_type}`",
             _note(c, lang)]
            for c in draft.columns]
    lines += md_table([tp(lang, "col_name"), tp(lang, "col_source"),
                       tp(lang, "col_ddl"), tp(lang, "col_note")], rows)
    lines += ["", f"### {tp(lang, 'rpt_ddl')}", "```sql",
              draft.ddl_text, "```", "", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
