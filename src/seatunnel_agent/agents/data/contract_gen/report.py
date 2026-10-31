"""Render a ContractDraft as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .generator import ContractDraft
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(draft: ContractDraft, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(tables=len(draft.tables),
                                          cols=draft.columns_total,
                                          cov=draft.comment_coverage,
                                          dialect=draft.dialect), "",
             f"### {tp(lang, 'rpt_tables')}"]
    rows = []
    for t in draft.tables:
        if t.require_comments:
            rule = tp(lang, "cmt_all")
        elif any(c.get("comment") for c in t.columns):
            rule = tp(lang, "cmt_keep")
        else:
            rule = tp(lang, "cmt_none")
        rows.append([f"`{t.name}`", str(len(t.columns)),
                     ", ".join(t.partitioned_by) or "-", rule,
                     f"{t.comment_coverage:.0%}"])
    lines += md_table([tp(lang, "col_table"), tp(lang, "col_cols"),
                       tp(lang, "col_parts"), tp(lang, "col_comments"),
                       tp(lang, "col_cov")], rows)
    lines += ["", f"### {tp(lang, 'rpt_yaml')}", "```yaml",
              draft.yaml_text.rstrip(), "```"]
    if draft.warnings:
        lines += ["", f"### {tp(lang, 'rpt_warnings')}"]
        lines += [f"- {w}" for w in draft.warnings[:5]]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
