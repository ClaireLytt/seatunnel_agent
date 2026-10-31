"""Render a WorkloadAdvice as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .advisor import WorkloadAdvice
from .i18n import tp

__all__ = ["render_audit", "render_markdown"]


def render_audit(findings: list[dict], lang: str = "zh") -> str:
    """Markdown section for advisor.audit findings."""
    lang = normalize_lang(lang)
    lines = [f"### {tp(lang, 'audit_title')}"]
    if not findings:
        lines.append(tp(lang, "audit_ok"))
        return "\n".join(lines)
    lines.extend(md_table(
        [tp(lang, "audit_col_code"), tp(lang, "audit_col_table"),
         tp(lang, "audit_col_detail"), tp(lang, "audit_col_meaning")],
        [[f["code"], f"`{f['table']}`", f"`{f['detail']}`",
          tp(lang, f["code"])] for f in findings]))
    return "\n".join(lines)


def render_markdown(advice: WorkloadAdvice, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    none = tp(lang, "none_mark")
    lines = [f"## {tp(lang, 'rpt_title')}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 statements=advice.statements, tables=len(advice.tables),
                 skipped=len(advice.skipped)) + "**",
             "",
             f"| {tp(lang, 'rpt_table_head')} "
             f"| {tp(lang, 'rpt_col_stmts')} "
             f"| {tp(lang, 'rpt_col_part')} "
             f"| {tp(lang, 'rpt_col_bucket')} "
             f"| {tp(lang, 'rpt_col_index')} |",
             "|---|---|---|---|---|"]
    for t in advice.tables:
        index = (", ".join(f"`{c}`" for c in t.index_cols)
                 if t.index_cols else none)
        lines.append(
            f"| `{t.table}` | {t.statements} "
            f"| {f'`{t.partition_col}`' if t.partition_col else none} "
            f"| {f'`{t.bucket_col}`' if t.bucket_col else none} "
            f"| {index} |")
    lines.append("")
    lines.append(f"### {tp(lang, 'rpt_hot_cols')}")
    for t in advice.tables:
        hot = " · ".join(
            f"`{name}` {s.eq}/{s.range}/{s.join}/{s.group}"
            for name, s in list(t.columns.items())[:5])
        lines.append(f"- `{t.table}`: {hot}")
    lines.append("")
    fragments = [(t.table, frag) for t in advice.tables for frag in t.ddl]
    if fragments:
        lines.append(f"### {tp(lang, 'rpt_ddl')}")
        lines.append("```sql")
        for table, frag in fragments:
            lines.append(f"-- {table}")
            lines.append(f"{frag};")
        lines.append("```")
        lines.append("")
    if advice.skipped:
        lines.append(f"### {tp(lang, 'rpt_skipped')}")
        lines.extend(f"- `{s}`" for s in advice.skipped)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
