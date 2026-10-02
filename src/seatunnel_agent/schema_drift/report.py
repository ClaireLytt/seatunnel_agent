# -*- coding: utf-8 -*-
"""Render DriftReport as markdown or a JSON-ready dict."""

from __future__ import annotations

from typing import Any

from .differ import DriftFinding, DriftReport
from .i18n import finding_message, normalize_lang, tp

_LEVEL_MARK = {"breaking": "⛔", "risk": "⚠️", "info": "ℹ️"}


def _finding_line(f: DriftFinding, lang: str) -> str:
    target = f"`{f.table}`" + (f" . `{f.column}`" if f.column else "")
    msg = finding_message(lang, f.kind, f.old, f.new)
    return f"- {_LEVEL_MARK[f.severity]} {target} — {msg}"


def render_markdown(report: DriftReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    c = report.counts()
    lines = [f"## 🧬 {tp(lang, 'rpt_title')}",
             f"{tp(lang, 'rpt_old')} `{report.old_root}` → "
             f"{tp(lang, 'rpt_new')} `{report.new_root}` · "
             f"{tp(lang, 'rpt_dialect')} `{report.dialect}`",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 tables_old=report.tables_old,
                 tables_new=report.tables_new, **c) + "**",
             ""]
    if not report.findings:
        lines.append(tp(lang, "rpt_clean"))
    for level, key in (("breaking", "rpt_breaking"), ("risk", "rpt_risk"),
                       ("info", "rpt_info")):
        group = [f for f in report.findings if f.severity == level]
        if not group:
            continue
        lines.append(f"### {_LEVEL_MARK[level]} {tp(lang, key)} "
                     f"({len(group)})")
        lines.extend(_finding_line(f, lang) for f in group)
        lines.append("")
    if report.warnings:
        lines.append(f"### ⚠️ {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in report.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def report_to_dict(report: DriftReport, lang: str = "zh") -> dict[str, Any]:
    """JSON payload: to_dict() plus rendered messages in the asked language."""
    lang = normalize_lang(lang)
    data = report.to_dict()
    for item, f in zip(data["findings"], report.findings):
        item["message"] = finding_message(lang, f.kind, f.old, f.new)
    return data
