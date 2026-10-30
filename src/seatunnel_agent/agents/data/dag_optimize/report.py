"""Render a DagOptimizeResult as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import normalize_lang

from .i18n import tp
from .optimizer import DagDiff, DagOptimizeResult

__all__ = ["render_diff_markdown", "render_markdown"]


def _num(value: float) -> str:
    return f"{value:g}"


def render_diff_markdown(diff: DagDiff, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    arrow = "↑" if diff.critical_delta > 0 else (
        "↓" if diff.critical_delta < 0 else "=")
    lines = [f"## {tp(lang, 'diff_title')}",
             "",
             "**" + tp(lang, "diff_stats").format(
                 before=_num(diff.critical_before),
                 after=_num(diff.critical_after),
                 delta=f"{arrow}{_num(abs(diff.critical_delta))}",
                 m2b=_num(diff.makespan2_before),
                 m2a=_num(diff.makespan2_after)) + "**",
             ""]
    for key, items in (
            ("diff_added_tasks", diff.added_tasks),
            ("diff_removed_tasks", diff.removed_tasks),
            ("diff_added_edges",
             [f"{u} → {d}" for u, d in diff.added_edges]),
            ("diff_removed_edges",
             [f"{u} → {d}" for u, d in diff.removed_edges])):
        if items:
            lines.append(f"- **{tp(lang, key)}**: "
                         + ", ".join(f"`{i}`" for i in items))
    if diff.new_redundant:
        lines.append(f"- **{tp(lang, 'diff_new_redundant')}**: "
                     + ", ".join(f"`{r.up}` → `{r.down}`"
                                 for r in diff.new_redundant))
    lines.append("")
    return "\n".join(lines)


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
    if result.deadline:
        if result.deadline_met and not result.deadline_plan:
            lines.append(tp(lang, "rpt_deadline_ok").format(
                deadline=_num(result.deadline),
                dur=_num(result.critical_duration)))
        elif result.deadline_met:
            plan = " → ".join(f"`{t}`" for t in result.deadline_plan)
            lines.append(tp(lang, "rpt_deadline_plan").format(
                deadline=_num(result.deadline), plan=plan))
        else:
            lines.append(tp(lang, "rpt_deadline_miss").format(
                deadline=_num(result.deadline),
                dur=_num(result.critical_duration)))
        lines.append("")
    if result.bottlenecks:
        lines.append(f"### {tp(lang, 'rpt_bottlenecks')}")
        lines.append(f"| {tp(lang, 'rpt_col_tasks')} "
                     f"| {tp(lang, 'rpt_col_duration')} "
                     f"| {tp(lang, 'rpt_col_halved')} "
                     f"| {tp(lang, 'rpt_col_gain')} |")
        lines.append("|---|---|---|---|")
        for b in result.bottlenecks:
            lines.append(f"| `{b['task']}` | {_num(b['duration'])} "
                         f"| {_num(b['halved_critical'])} "
                         f"| -{_num(b['gain'])} |")
        lines.append("")
    if result.makespans:
        lines.append(f"### {tp(lang, 'rpt_makespan')}")
        lines.append(f"| {tp(lang, 'rpt_col_workers')} "
                     f"| {tp(lang, 'rpt_col_makespan')} "
                     f"| {tp(lang, 'rpt_col_speedup')} |")
        lines.append("|---|---|---|")
        serial = result.makespans.get("1", 0.0)
        for k, span in result.makespans.items():
            label = "∞" if k == "inf" else k
            gain = f"{serial / span:.2f}x" if span else "-"
            lines.append(f"| {label} | {_num(span)} | {gain} |")
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
    if result.optimized:
        lines.append(f"### {tp(lang, 'rpt_optimized')}")
        lines.append("```json")
        lines.append(json.dumps(result.optimized, ensure_ascii=False,
                                indent=2))
        lines.append("```")
        lines.append("")
    if result.warnings:
        lines.append(f"### {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in result.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
