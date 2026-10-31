"""Render a StrategyReport as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang

from .advisor import StrategyReport
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(result: StrategyReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = result.counts()
    lines = [f"## {tp(lang, 'rpt_title')}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 tables=len(result.recommendations), **counts) + "**",
             ""]
    moved, full = result.fleet_rows()
    if full:
        lines.append(tp(lang, "rpt_fleet").format(
            moved=f"{moved:,}", full=f"{full:,}",
            pct=f"{(1 - moved / full) * 100:.1f}"))
        lines.append("")
    lines.extend([
        f"| {tp(lang, 'rpt_col_table')} "
        f"| {tp(lang, 'rpt_col_strategy')} "
        f"| {tp(lang, 'rpt_col_schedule')} "
        f"| {tp(lang, 'rpt_col_rows')} "
        f"| {tp(lang, 'rpt_col_reasons')} "
        f"| {tp(lang, 'rpt_col_risks')} |",
        "|---|---|---|---|---|---|"])
    for rec in result.recommendations:
        reasons = "; ".join(tp(lang, "reason_" + r) for r in rec.reasons)
        risks = ("; ".join(tp(lang, "risk_" + r) for r in rec.risks)
                 if rec.risks else "-")
        schedule = (tp(lang, "schedule_streaming")
                    if rec.schedule == "streaming" else f"`{rec.schedule}`")
        if rec.rows_per_sync < 0:
            rows = "-"
        elif rec.strategy == "full":
            rows = f"{rec.rows_per_sync:,}"
        else:
            rows = (f"{rec.rows_per_sync:,} "
                    + tp(lang, "rows_saving").format(
                        pct=f"{rec.saving_ratio * 100:.1f}"))
        lines.append(f"| `{rec.table}` "
                     f"| **{tp(lang, 'strategy_' + rec.strategy)}** "
                     f"| {schedule} | {rows} | {reasons} | {risks} |")
    lines.append("")
    lines.append(f"### {tp(lang, 'rpt_configs')}")
    for rec in result.recommendations:
        if not rec.config:
            continue
        lines.append(f"**`{rec.table}` — "
                     f"{tp(lang, 'strategy_' + rec.strategy)}**")
        lines.append("```hocon")
        lines.append(rec.config)
        lines.append("```")
    lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
