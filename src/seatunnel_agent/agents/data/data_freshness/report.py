"""Render a FreshnessScan as markdown or a JSON-ready dict."""

from __future__ import annotations

from typing import Any

from seatunnel_agent.common.utils import normalize_lang

from .checker import GRACE_FACTOR, STALL_FACTOR, FreshnessScan, TableFreshness
from .i18n import tp


def _fmt_s(seconds: float | None) -> str:
    """Compact duration: 95 -> 1m35s, 4000 -> 1h06m, 200000 -> 2d07h."""
    if seconds is None:
        return "-"
    s = int(round(abs(seconds)))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    if s < 86400:
        return f"{s // 3600}h{(s % 3600) // 60:02d}m"
    return f"{s // 86400}d{(s % 86400) // 3600:02d}h"


def _detail(lang: str, t: TableFreshness) -> str:
    if t.detail == "no_update":
        return tp(lang, "detail_no_update").format(factor=STALL_FACTOR)
    if t.detail == "over_max_age":
        return tp(lang, "detail_over_max_age").format(
            max_age=_fmt_s(t.max_age_s))
    if t.detail == "gap_over_interval":
        return tp(lang, "detail_gap_over_interval").format(
            gap=_fmt_s(t.last_gap_s), interval=_fmt_s(t.interval_s))
    if t.detail == "no_cadence":
        return tp(lang, "detail_no_cadence")
    return ""


def _cadence(lang: str, t: TableFreshness) -> str:
    if t.interval_s is None:
        return "-"
    return f"{_fmt_s(t.interval_s)} ({tp(lang, 'src_' + t.interval_src)})"


def render_markdown(result: FreshnessScan, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}",
             f"{tp(lang, 'rpt_now')} `{result.now.isoformat(sep=' ')}`",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 tables=len(result.tables),
                 stalled=result.count("stalled"),
                 stale=result.count("stale"),
                 late=result.count("late"),
                 unknown=result.count("unknown"),
                 ok=result.count("ok")) + "**",
             ""]
    findings = [t for t in result.tables if t.verdict != "ok"]
    if findings:
        lines.append(f"### {tp(lang, 'rpt_findings')}")
        lines.append(f"| {tp(lang, 'rpt_col_table')} "
                     f"| {tp(lang, 'rpt_col_verdict')} "
                     f"| {tp(lang, 'rpt_col_last')} "
                     f"| {tp(lang, 'rpt_col_age')} "
                     f"| {tp(lang, 'rpt_col_interval')} "
                     f"| {tp(lang, 'rpt_col_detail')} |")
        lines.append("|---|---|---|---|---|---|")
        for t in findings:
            lines.append(
                f"| `{t.table}` | **{tp(lang, 'verdict_' + t.verdict)}** "
                f"| {t.last_updated.isoformat(sep=' ')} | {_fmt_s(t.age_s)} "
                f"| {_cadence(lang, t)} | {_detail(lang, t)} |")
        lines.append("")
    else:
        lines.append(tp(lang, "rpt_all_ok"))
        lines.append("")
    ok_tables = [t for t in result.tables if t.verdict == "ok"]
    if ok_tables and findings:
        lines.append(f"### {tp(lang, 'rpt_ok_tables')}")
        lines.append(", ".join(f"`{t.table}`" for t in ok_tables))
        lines.append("")
    if result.warnings:
        lines.append(f"### {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in result.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def scan_to_dict(result: FreshnessScan) -> dict[str, Any]:
    return {
        "now": result.now.isoformat(sep=" "),
        "tables": [t.to_dict() for t in result.tables],
        "counts": {v: result.count(v)
                   for v in ("stalled", "stale", "late", "unknown", "ok")},
        "worst": result.worst(),
        "stall_factor": STALL_FACTOR,
        "grace_factor": GRACE_FACTOR,
        "warnings": list(result.warnings),
    }
