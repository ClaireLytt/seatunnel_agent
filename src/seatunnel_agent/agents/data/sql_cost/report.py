"""Render a CostCard as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import fmt_bytes, fmt_secs, normalize_lang

from .estimator import CostCard
from .i18n import tp

__all__ = ["render_markdown", "render_what_if"]


def render_markdown(card: CostCard, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 scan=fmt_bytes(card.scan_bytes),
                 shuffle=fmt_bytes(card.shuffle_bytes),
                 rows=f"{card.output_rows:,.0f}",
                 core_s=f"{card.core_seconds:,.0f}") + "**",
             "",
             tp(lang, "rpt_verdict").format(
                 par=card.parallelism,
                 lo=fmt_secs(card.wall_seconds[0]),
                 hi=fmt_secs(card.wall_seconds[1]),
                 mem=fmt_bytes(card.memory_peak_bytes)),
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
            lines.append(f"| `{s.table}` | {fmt_bytes(s.bytes)} "
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


def render_what_if(whatif: dict, lang: str = "zh") -> str:
    """Markdown section for a what-if delta from estimator.what_if."""
    lang = normalize_lang(lang)
    lines = [f"### {tp(lang, 'wi_title')}"]
    lines += [f"- `{s}`" for s in whatif["assumed"]]
    before = whatif["base_scan_bytes"]
    lines.append("")
    lines.append(tp(lang, "wi_scan").format(
        before=fmt_bytes(before), after=fmt_bytes(whatif["scan_bytes"]),
        pct=f"{whatif['scan_saved_pct']:g}"))
    if whatif["scan_saved_pct"] <= 0:
        lines.append("")
        lines.append(tp(lang, "wi_no_save"))
    return "\n".join(lines)
