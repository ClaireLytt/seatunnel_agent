"""Render a DictResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .generator import DictResult
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(result: DictResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    coverage = (sum(t.comment_coverage for t in result.tables)
                / len(result.tables)) if result.tables else 0.0
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(tables=len(result.tables),
                                          coverage=f"{coverage:.0f}"), ""]
    for t in result.tables:
        key = "rpt_table" if t.comment else "rpt_table_nocmt"
        lines.append("### " + tp(lang, key).format(
            table=t.table, comment=t.comment,
            coverage=f"{t.comment_coverage:.0f}"))
        rows = []
        for e in t.entries:
            usage = f"{e.filter_uses}/{e.join_uses}/{e.group_uses}"
            rows.append([f"`{e.name}`", tp(lang, "role_" + e.role),
                         e.comment or "—", usage])
        lines += md_table([tp(lang, "col_name"), tp(lang, "col_role"),
                           tp(lang, "col_comment"), tp(lang, "col_usage")],
                          rows)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
