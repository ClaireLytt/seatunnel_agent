"""Render a MigrationReport as markdown."""

from __future__ import annotations

import json

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
    if result.migration_order:
        lines.append(f"### {tp(lang, 'rpt_order')}")
        for i, wave in enumerate(result.migration_order, 1):
            lines.append(f"{i}. " + ", ".join(f"`{j}`" for j in wave))
        lines.append("")
    if result.shared_tables:
        lines.append(f"### {tp(lang, 'rpt_shared')}")
        for s in result.shared_tables:
            consumers = ", ".join(f"`{c}`" for c in s["consumers"])
            lines.append(f"- `{s['table']}`: `{s['producer']}` → {consumers}")
        lines.append("")
    stubs = [j for j in result.jobs if j.stub]
    if stubs:
        lines.append(f"### {tp(lang, 'rpt_stubs')}")
        for job in stubs:
            lines.append(f"**`{job.job}`**")
            lines.append("```hocon")
            lines.append(job.stub)
            lines.append("```")
        lines.append("")
    if result.migration_dag:
        lines.append(f"### {tp(lang, 'rpt_migration_dag')}")
        lines.append("```json")
        lines.append(json.dumps(result.migration_dag, ensure_ascii=False,
                                indent=2))
        lines.append("```")
        lines.append("")
    if result.warnings:
        lines.append(f"### {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in result.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
