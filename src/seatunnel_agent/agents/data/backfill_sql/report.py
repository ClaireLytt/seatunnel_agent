"""Render a BackfillSql result as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang

from .generator import BackfillSql
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(result: BackfillSql, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    n_stmt = sum(len(d.statements) for d in result.dates)
    lines = [f"## {tp(lang, 'rpt_title')}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 table=result.table, mode=result.mode,
                 dialect=result.dialect, dates=len(result.dates),
                 statements=n_stmt) + "**",
             ""]
    if result.warnings:
        lines.append(f"### {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in result.warnings)
        lines.append("")
    if result.prechecks:
        lines.append(f"### {tp(lang, 'rpt_prechecks')}")
        lines.append("```sql")
        lines.append("\n\n".join(result.prechecks))
        lines.append("```")
        lines.append("")
    lines.append(f"### {tp(lang, 'rpt_sql')}")
    for d in result.dates:
        lines.append(f"**{tp(lang, 'rpt_date')} {d.date} — "
                     f"`{d.partition_value}`**")
        lines.append("```sql")
        lines.append("\n".join(d.statements))
        lines.append("```")
    lines.append("")
    if result.postchecks:
        lines.append(f"### {tp(lang, 'rpt_postchecks')}")
        lines.append("```sql")
        lines.append("\n\n".join(result.postchecks))
        lines.append("```")
        lines.append("")
    if result.runner_script:
        lines.append(f"### {tp(lang, 'rpt_runner')}")
        lines.append("```bash")
        lines.append(result.runner_script)
        lines.append("```")
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
