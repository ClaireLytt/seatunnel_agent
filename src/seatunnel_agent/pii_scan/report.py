# -*- coding: utf-8 -*-
"""Render PiiReport as markdown or a JSON-ready dict."""

from __future__ import annotations

from typing import Any

from .i18n import category_label, normalize_lang, tp
from .scanner import PiiFinding, PiiReport

_LEVEL_MARK = {"high": "⛔", "medium": "⚠️", "low": "🔵"}
_MATCH_KEY = {"name": "rpt_matched_name", "comment": "rpt_matched_comment",
              "name+comment": "rpt_matched_both"}


def _finding_lines(f: PiiFinding, lang: str) -> list[str]:
    cat = category_label(lang, f.category)
    how = tp(lang, _MATCH_KEY.get(f.matched_by, "rpt_matched_name"))
    weak = f" ({tp(lang, 'rpt_weak')})" if f.confidence == "low" else ""
    head = (f"- {_LEVEL_MARK[f.severity]} `{f.table}.{f.column}` "
            f"【{cat}】 {how} `{f.evidence}`{weak}")
    if f.comment:
        head += f" — “{f.comment}”"
    lines = [head]
    if f.spread_edges:
        unmasked = len(f.unmasked_edges)
        key = "rpt_spread" if unmasked else "rpt_spread_masked"
        lines.append("    - " + tp(lang, key).format(
            n=len(f.impacted), unmasked=unmasked))
        for e in f.spread_edges:
            expr = e.expression or tp(lang, "rpt_direct_copy")
            state = (f"✅ {tp(lang, 'rpt_masked')}" if e.masked
                     else f"❌ {tp(lang, 'rpt_unmasked')}")
            lines.append(f"    - ➜ `{e.dst}` (`{expr}`, {state})")
        if f.severity != f.base_severity:
            lines.append(f"    - ⬆️ {tp(lang, 'rpt_escalated')}")
    else:
        lines.append("    - " + tp(lang, "rpt_no_spread"))
    return lines


def render_markdown(report: PiiReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    c = report.counts()
    lines = [f"## 🔒 {tp(lang, 'rpt_title')}",
             f"{tp(lang, 'rpt_root')} `{report.root}` · "
             f"{tp(lang, 'rpt_dialect')} `{report.dialect}`",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 tables=report.tables_scanned,
                 columns=report.columns_scanned, **c) + "**",
             ""]
    if not report.findings:
        lines.append(tp(lang, "rpt_clean"))
    for level, key in (("high", "rpt_high"), ("medium", "rpt_medium"),
                       ("low", "rpt_low")):
        group = [f for f in report.findings if f.severity == level]
        if not group:
            continue
        lines.append(f"### {_LEVEL_MARK[level]} {tp(lang, key)} "
                     f"({len(group)})")
        for f in group:
            lines.extend(_finding_lines(f, lang))
        lines.append("")
    if report.warnings:
        lines.append(f"### ⚠️ {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in report.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def report_to_dict(report: PiiReport, lang: str = "zh") -> dict[str, Any]:
    """JSON payload: to_dict() plus localized category labels."""
    lang = normalize_lang(lang)
    data = report.to_dict()
    for item in data["findings"]:
        item["category_label"] = category_label(lang, item["category"])
    return data
