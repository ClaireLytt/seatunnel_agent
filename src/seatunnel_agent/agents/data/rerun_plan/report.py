"""Render a RerunPlan as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang

from .i18n import tp
from .planner import RerunPlan

__all__ = ["render_markdown"]


def render_markdown(result: RerunPlan, lang: str = "zh",
                    cmd_template: str = "") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 rerun=len(result.tasks), total=result.total,
                 batches=result.batches,
                 radius=f"{result.blast_radius * 100:g}",
                 untouched=len(result.untouched)) + "**",
             ""]
    if result.total_eta:
        etas = " + ".join(f"{e:g}" for e in result.batch_etas)
        lines.append(tp(lang, "rpt_eta").format(
            total=f"{result.total_eta:g}", batches=etas))
        lines.append("")
    if result.tasks:
        lines.append(f"### {tp(lang, 'rpt_steps')}")
        lines.append(f"| {tp(lang, 'rpt_col_batch')} "
                     f"| {tp(lang, 'rpt_col_task')} "
                     f"| {tp(lang, 'rpt_col_reason')} "
                     f"| {tp(lang, 'rpt_col_from')} |")
        lines.append("|---|---|---|---|")
        for t in result.tasks:
            reason = tp(lang, "reason_" + t.reason)
            if t.stale_success:
                reason += tp(lang, "stale_note")
            frm = (", ".join(f"`{r}`" for r in t.from_failed)
                   if t.from_failed else "-")
            lines.append(f"| {t.batch} | `{t.task}` | {reason} | {frm} |")
        lines.append("")
        if cmd_template.strip():
            lines.append(f"### {tp(lang, 'rpt_commands')}")
            lines.append("```bash")
            lines.extend(result.commands(cmd_template.strip()))
            lines.append("```")
            lines.append("")
    if result.untouched:
        lines.append(f"### {tp(lang, 'rpt_untouched')}")
        lines.append(", ".join(f"`{n}`" for n in result.untouched))
        lines.append("")
    if result.unschedulable:
        lines.append(f"### {tp(lang, 'rpt_unschedulable')}")
        lines.append(", ".join(f"`{n}`" for n in result.unschedulable))
        lines.append("")
    if result.warnings:
        lines.append(f"### {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in result.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
