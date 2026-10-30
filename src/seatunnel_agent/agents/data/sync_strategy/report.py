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
             "",
             f"| {tp(lang, 'rpt_col_table')} "
             f"| {tp(lang, 'rpt_col_strategy')} "
             f"| {tp(lang, 'rpt_col_reasons')} "
             f"| {tp(lang, 'rpt_col_risks')} |",
             "|---|---|---|---|"]
    for rec in result.recommendations:
        reasons = "; ".join(tp(lang, "reason_" + r) for r in rec.reasons)
        risks = ("; ".join(tp(lang, "risk_" + r) for r in rec.risks)
                 if rec.risks else "-")
        lines.append(f"| `{rec.table}` "
                     f"| **{tp(lang, 'strategy_' + rec.strategy)}** "
                     f"| {reasons} | {risks} |")
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
