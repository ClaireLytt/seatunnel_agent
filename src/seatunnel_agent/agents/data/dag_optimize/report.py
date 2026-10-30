"""Render a DagOptimizeResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang

from .i18n import tp
from .optimizer import DagOptimizeResult

__all__ = ["render_markdown"]


def _num(value: float) -> str:
    return f"{value:g}"


def render_markdown(result: DagOptimizeResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 tasks=result.tasks, edges=result.edges,
                 redundant=len(result.redundant),
                 waves=len(result.batches), width=result.max_width,
                 speedup=_num(result.speedup)) + "**",
             ""]
    lines.append(f"### {tp(lang, 'rpt_redundant')}")
    if result.redundant:
        lines.append(f"| {tp(lang, 'rpt_col_edge')} "
                     f"| {tp(lang, 'rpt_col_via')} |")
        lines.append("|---|---|")
        for r in result.redundant:
            via = " → ".join(f"`{n}`" for n in r.via)
            lines.append(f"| `{r.up}` → `{r.down}` | {via} |")
    else:
        lines.append(tp(lang, "rpt_no_redundant"))
    lines.append("")
    if result.batches:
        lines.append(f"### {tp(lang, 'rpt_waves')}")
        lines.append(f"| {tp(lang, 'rpt_col_wave')} "
                     f"| {tp(lang, 'rpt_col_width')} "
                     f"| {tp(lang, 'rpt_col_tasks')} |")
        lines.append("|---|---|---|")
        for i, batch in enumerate(result.batches, 1):
            tasks = ", ".join(f"`{n}`" for n in batch)
            lines.append(f"| {i} | {len(batch)} | {tasks} |")
        lines.append("")
    if result.critical_path:
        lines.append(f"### {tp(lang, 'rpt_critical')}")
        lines.append(" → ".join(f"`{n}`" for n in result.critical_path))
        lines.append("")
        lines.append(tp(lang, "rpt_critical_note").format(
            dur=_num(result.critical_duration),
            total=_num(result.total_duration)))
        lines.append("")
    if result.chains:
        lines.append(f"### {tp(lang, 'rpt_chains')}")
        for chain in result.chains:
            lines.append("- " + " → ".join(f"`{n}`" for n in chain))
        lines.append("")
    if result.cycles:
        lines.append(f"### {tp(lang, 'rpt_cycles')}")
        lines.append(", ".join(f"`{n}`" for n in result.cycles))
        lines.append("")
    if result.warnings:
        lines.append(f"### {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in result.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
