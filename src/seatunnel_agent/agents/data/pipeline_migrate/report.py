"""Render a MigrationReport as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang

from .assessor import MigrationReport
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(result: MigrationReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = result.counts()
    efforts = result.effort_counts()
    lines = [f"## {tp(lang, 'rpt_title')}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 jobs=len(result.jobs), s=efforts["S"], m=efforts["M"],
                 l=efforts["L"], **counts) + "**",
             "",
             f"### {tp(lang, 'rpt_jobs')}",
             f"| {tp(lang, 'rpt_col_job')} "
             f"| {tp(lang, 'rpt_col_target')} "
             f"| {tp(lang, 'rpt_col_effort')} "
             f"| {tp(lang, 'rpt_col_why')} "
             f"| {tp(lang, 'rpt_col_risks')} |",
             "|---|---|---|---|---|"]
    for job in result.jobs:
        why = "; ".join(tp(lang, "reason_" + r) for r in job.reasons)
        risks = ("; ".join(tp(lang, "risk_" + r) for r in job.risks)
                 if job.risks else "-")
        lines.append(f"| `{job.job}` "
                     f"| **{tp(lang, 'target_' + job.target)}** "
                     f"| {job.effort} ({job.score}) | {why} | {risks} |")
    lines.append("")
    if result.warnings:
        lines.append(f"### {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in result.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
