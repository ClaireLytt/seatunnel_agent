# -*- coding: utf-8 -*-
"""Render MetricReport as markdown or a JSON-ready dict."""

from __future__ import annotations

from typing import Any

from .differ import MetricReport
from .i18n import normalize_lang, tp

_LEVEL_MARK = {"high": "⛔", "medium": "⚠️"}


def render_markdown(report: MetricReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    c = report.counts()
    lines = [f"## 📏 {tp(lang, 'rpt_title')}",
             f"{tp(lang, 'rpt_root')} `{report.root}` · "
             f"{tp(lang, 'rpt_dialect')} `{report.dialect}`",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 metrics=report.metrics_checked,
                 consistent=report.consistent, **c) + "**",
             ""]
    if not report.conflicts:
        lines.append(tp(lang, "rpt_clean"))
        lines.append("")
    for conflict in report.conflicts:
        mark = _LEVEL_MARK[conflict.severity]
        msg = tp(lang, f"msg_{conflict.kind}")
        lines.append(f"### {mark} `{conflict.name}` — {msg}")
        for d in conflict.defs:
            origins = ", ".join(o.removeprefix("sql:") for o in d.origins)
            lines.append(
                f"- {tp(lang, 'rpt_defined_in')} `{d.table}`"
                + (f" ({origins})" if origins else "")
                + f": `{d.expression}` — {tp(lang, 'rpt_from')} "
                + ", ".join(f"`{s}`" for s in d.sources))
        lines.append("")
    if report.warnings:
        lines.append(f"### ⚠️ {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in report.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def report_to_dict(report: MetricReport, lang: str = "zh") -> dict[str, Any]:
    lang = normalize_lang(lang)
    data = report.to_dict()
    for item in data["conflicts"]:
        item["message"] = tp(lang, f"msg_{item['kind']}")
    return data
