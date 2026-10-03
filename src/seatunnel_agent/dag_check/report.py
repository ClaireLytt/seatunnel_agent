# -*- coding: utf-8 -*-
"""Render DagReport as markdown or a JSON-ready dict."""

from __future__ import annotations

from typing import Any

from .checker import DagReport
from .i18n import normalize_lang, tp

_LEVEL_MARK = {"error": "⛔", "warn": "⚠️", "info": "ℹ️"}


def render_markdown(report: DagReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    c = report.counts()
    lines = [f"## 🗓️ {tp(lang, 'rpt_title')}",
             f"{tp(lang, 'rpt_root')} `{report.root}`",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 tables=report.tables, edges=report.edges, **c) + "**",
             ""]
    if not report.findings:
        lines.append(tp(lang, "rpt_clean"))
        lines.append("")
    else:
        lines.append(f"### {tp(lang, 'rpt_findings')}")
        for f in report.findings:
            mark = _LEVEL_MARK[f.severity]
            msg = tp(lang, f"msg_{f.kind}")
            if f.kind == "cycle":
                tables = f.tables
                # close the loop only when find_cycles didn't already
                if tables and tables[0] != tables[-1]:
                    tables = tables + tables[:1]
                lines.append(f"- {mark} {msg}: `{' → '.join(tables)}`")
            else:
                tables = " · ".join(f"`{t}`" for t in f.tables[:10])
                more = f" (+{len(f.tables) - 10})" if len(f.tables) > 10 else ""
                lines.append(f"- {mark} {msg}: {tables}{more}")
        lines.append("")
    if report.batches:
        lines.append(f"### {tp(lang, 'rpt_batches')}")
        for i, batch in enumerate(report.batches, start=1):
            tables = " · ".join(f"`{t}`" for t in batch)
            lines.append(f"- {tp(lang, 'rpt_batch')} {i}: {tables}")
        lines.append("")
    if report.unschedulable:
        lines.append(f"### ⛔ {tp(lang, 'rpt_unschedulable')}")
        lines.append(" · ".join(f"`{t}`" for t in report.unschedulable))
        lines.append("")
    if len(report.critical_path) > 1:
        lines.append(f"### {tp(lang, 'rpt_critical')} "
                     f"({len(report.critical_path)})")
        lines.append(" → ".join(f"`{t}`" for t in report.critical_path))
        lines.append("")
    if report.warnings:
        lines.append(f"### ⚠️ {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in report.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def report_to_dict(report: DagReport, lang: str = "zh") -> dict[str, Any]:
    lang = normalize_lang(lang)
    data = report.to_dict()
    for item in data["findings"]:
        item["message"] = tp(lang, f"msg_{item['kind']}")
    return data
