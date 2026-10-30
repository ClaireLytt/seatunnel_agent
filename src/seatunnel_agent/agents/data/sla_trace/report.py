"""Render an SlaTrace as markdown or a JSON-ready dict."""

from __future__ import annotations

from typing import Any

from seatunnel_agent.common.utils import normalize_lang

from .i18n import tp
from .tracer import SlaTrace


def _fmt_s(seconds: float) -> str:
    """Compact duration: 95 -> 1m35s, 4000 -> 1h6m."""
    s = int(round(abs(seconds)))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


def render_markdown(result: SlaTrace, lang: str = "zh",
                    top: int = 5) -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}",
             f"{tp(lang, 'rpt_target')} `{result.target}`",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 instances=result.instances, steps=len(result.path),
                 total=_fmt_s(result.total_s)) + "**",
             ""]
    if result.deadline is not None and result.finished_at is not None:
        key = "rpt_sla_breach" if result.breach_s > 0 else "rpt_sla_ok"
        lines.append("**" + tp(lang, key).format(
            end=result.finished_at.isoformat(sep=" "),
            deadline=result.deadline.isoformat(sep=" "),
            late=_fmt_s(result.breach_s),
            margin=_fmt_s(result.breach_s)) + "**")
        lines.append("")
    total = result.total_s or 1.0
    if result.path:
        lines.append(f"### {tp(lang, 'rpt_top')}")
        lines.append(f"| # | {tp(lang, 'rpt_col_task')} "
                     f"| {tp(lang, 'rpt_col_wait')} "
                     f"| {tp(lang, 'rpt_col_run')} "
                     f"| {tp(lang, 'rpt_col_share')} |")
        lines.append("|---|---|---|---|---|")
        for i, (step, contrib) in enumerate(result.top_delays(top), start=1):
            lines.append(
                f"| {i} | `{step.task.name}` | {_fmt_s(step.wait_s)} "
                f"| {_fmt_s(step.task.run_s)} "
                f"| {contrib / total * 100:.0f}% |")
        lines.append("")
        lines.append(f"### {tp(lang, 'rpt_path')}")
        for step in result.path:
            on = step.blocking or tp(lang, "rpt_path_root")
            lines.append("- " + tp(lang, "rpt_path_step").format(
                name=f"`{step.task.name}`", on=f"`{on}`",
                wait=_fmt_s(step.wait_s), run=_fmt_s(step.task.run_s)))
        lines.append("")
    if result.warnings:
        lines.append(f"### {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in result.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def trace_to_dict(result: SlaTrace) -> dict[str, Any]:
    return {
        "target": result.target,
        "instances": result.instances,
        "total_s": round(result.total_s, 1),
        "finished_at": (result.finished_at.isoformat(sep=" ")
                        if result.finished_at else None),
        "deadline": (result.deadline.isoformat(sep=" ")
                     if result.deadline else None),
        "breach_s": round(result.breach_s, 1),
        "path": [s.to_dict() for s in result.path],
        "warnings": list(result.warnings),
    }
