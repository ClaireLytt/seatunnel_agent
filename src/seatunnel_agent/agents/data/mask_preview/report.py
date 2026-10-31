"""Render a MaskPreview as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .masker import MaskPreview

__all__ = ["render_markdown"]


def render_markdown(preview: MaskPreview, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(rows=preview.rows_total,
                                          cols=len(preview.headers),
                                          sensitive=len(preview.columns))]
    if preview.clean:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_columns')}"]
        rows = [[SEVERITY_MARK[c.severity], f"`{c.name}`", c.category,
                 tp(lang, "by_" + c.detected_by),
                 f"`{c.sample_before}`" if c.sample_before else "-",
                 f"`{c.sample_after}`" if c.sample_after else "-"]
                for c in preview.columns]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_name"),
                           tp(lang, "col_category"), tp(lang, "col_by"),
                           tp(lang, "col_before"), tp(lang, "col_after")],
                          rows)
        n = len(preview.masked_rows)
        lines += ["", f"### {tp(lang, 'rpt_preview').format(n=n)}"]
        body = [[str(r.get(h) if r.get(h) is not None else "")
                 for h in preview.headers] for r in preview.masked_rows]
        lines += md_table(list(preview.headers), body)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
