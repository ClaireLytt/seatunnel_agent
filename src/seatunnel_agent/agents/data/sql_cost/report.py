"""Render a CostCard as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang

from .estimator import CostCard
from .i18n import tp

__all__ = ["render_markdown"]


def _size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{num:.0f} B"
        num /= 1024
    return f"{num:.1f} TB"


def _secs(s: float) -> str:
    if s < 90:
        return f"{s:.0f}s"
    if s < 5400:
        return f"{s / 60:.1f}min"
    return f"{s / 3600:.1f}h"


def render_markdown(card: CostCard, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 scan=_size(card.scan_bytes),
                 shuffle=_size(card.shuffle_bytes),
                 rows=f"{card.output_rows:,.0f}",
                 core_s=f"{card.core_seconds:,.0f}") + "**",
             "",
             tp(lang, "rpt_verdict").format(
                 par=card.parallelism,
                 lo=_secs(card.wall_seconds[0]),
                 hi=_secs(card.wall_seconds[1]),
                 mem=_size(card.memory_peak_bytes)),
             ""]
    if card.scans:
        lines.append(f"### {tp(lang, 'rpt_scans')}")
        lines.append(f"| {tp(lang, 'rpt_col_table')} "
                     f"| {tp(lang, 'rpt_col_bytes')} "
                     f"| {tp(lang, 'rpt_col_rows')} "
                     f"| {tp(lang, 'rpt_col_pruned')} "
                     f"| {tp(lang, 'rpt_col_colratio')} |")
        lines.append("|---|---|---|---|---|")
        for s in card.scans:
            pruned = (tp(lang, "yes") if s.pruned
                      else f"**{tp(lang, 'no')}**")
            lines.append(f"| `{s.table}` | {_size(s.bytes)} "
                         f"| {s.rows:,.0f} | {pruned} "
                         f"| {s.col_ratio:.0%} |")
        lines.append("")
    if card.missing:
        lines.append(f"### {tp(lang, 'rpt_missing')}")
        lines.append(", ".join(f"`{t}`" for t in card.missing))
        lines.append("")
    lines.append(f"### {tp(lang, 'rpt_assumptions')}")
    lines.append(tp(lang, "asm_lines"))
    lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
