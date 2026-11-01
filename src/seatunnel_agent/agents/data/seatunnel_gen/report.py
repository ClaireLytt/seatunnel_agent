"""Render a ConfigDraft as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .generator import ConfigDraft
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(draft: ConfigDraft, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(source=draft.source,
                                          sink=draft.sink,
                                          table=draft.table,
                                          columns=draft.columns,
                                          mode=draft.job_mode,
                                          errors=draft.lint_errors,
                                          warns=draft.lint_warns), "",
             f"### {tp(lang, 'rpt_params')}"]
    rows = ([[f"`{p}`", tp(lang, "state_filled")] for p in draft.filled]
            + [[f"`{p}`", tp(lang, "state_placeholder")]
               for p in draft.placeholders])
    lines += md_table([tp(lang, "col_param"), tp(lang, "col_state")], rows)
    lines += ["", f"### {tp(lang, 'rpt_hocon')}", "```hocon",
              draft.hocon_text.rstrip(), "```"]
    if draft.warnings:
        lines += ["", f"### {tp(lang, 'rpt_warnings')}"]
        lines += [f"- {w}" for w in draft.warnings[:5]]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
