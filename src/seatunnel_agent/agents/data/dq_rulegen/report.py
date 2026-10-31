"""Render a RuleDraft as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .generator import RuleDraft
from .i18n import tp

__all__ = ["render_markdown"]


def _params(c) -> str:
    if c.type == "enum_domain":
        vals = c.params.get("allowed", [])
        shown = ", ".join(str(v) for v in vals[:6])
        if len(vals) > 6:
            shown += ", …"
        return shown
    return ", ".join(f"{k}={v:g}" for k, v in c.params.items()) or "-"


def render_markdown(draft: RuleDraft, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(table=draft.table,
                                          rows=draft.rows_sampled,
                                          checks=len(draft.checks)), "",
             f"### {tp(lang, 'rpt_checks')}"]
    rows = [[c.type,
             "`" + (c.column or ", ".join(c.columns) or draft.table) + "`",
             _params(c), c.basis or "-"]
            for c in draft.checks]
    lines += md_table([tp(lang, "col_type"), tp(lang, "col_target"),
                       tp(lang, "col_params"), tp(lang, "col_basis")],
                      rows)
    lines += ["", f"### {tp(lang, 'rpt_yaml')}", "```yaml",
              draft.yaml_text.rstrip(), "```"]
    if draft.skipped:
        lines += ["", f"### {tp(lang, 'rpt_skipped')}"]
        lines += [f"- {s}" for s in draft.skipped]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
