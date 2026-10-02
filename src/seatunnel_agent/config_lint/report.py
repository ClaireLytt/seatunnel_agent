# -*- coding: utf-8 -*-
"""Render LintResult(s) as markdown or JSON-ready dicts."""

from __future__ import annotations

from typing import Any, Iterable

from .i18n import finding_message, normalize_lang, tp
from .linter import LintFinding, LintResult

_LEVEL_MARK = {"error": "⛔", "warn": "⚠️", "info": "ℹ️"}


def _finding_line(f: LintFinding, lang: str) -> str:
    where = f.section or "-"
    if f.connector:
        where += f" / {f.connector}"
    if f.param:
        where += f" / {f.param}"
    msg = finding_message(lang, f.kind, f.message_params)
    return f"- {_LEVEL_MARK[f.severity]} `{where}` — {msg}"


def render_markdown(result: LintResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    c = result.counts()
    verdict = tp(lang, "rpt_ok") if result.ok else tp(lang, "rpt_fail")
    mark = "✅" if result.ok else "⛔"
    lines = [f"## 🧰 {tp(lang, 'rpt_title')} — {mark} {verdict}",
             f"`{result.name}`",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 connectors=len(result.connectors), **c) + "**",
             ""]
    if not result.findings:
        lines.append(tp(lang, "rpt_clean"))
    else:
        lines.extend(_finding_line(f, lang) for f in result.findings)
    lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def render_batch_markdown(results: Iterable[LintResult],
                          lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    results = list(results)
    total = {"error": 0, "warn": 0, "info": 0, "total": 0}
    for r in results:
        for k, v in r.counts().items():
            total[k] += v
    passed = sum(1 for r in results if r.ok)
    lines = [f"## 🧰 {tp(lang, 'rpt_title')}", "",
             "**" + tp(lang, "rpt_batch_stats").format(
                 files=len(results), passed=passed, **total) + "**", ""]
    lines.append("| | file | error | warn | info |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        c = r.counts()
        mark = "✅" if r.ok else "⛔"
        lines.append(f"| {mark} | `{r.name}` | {c['error']} | {c['warn']} "
                     f"| {c['info']} |")
    lines.append("")
    for r in results:
        if not r.findings:
            continue
        lines.append(f"### `{r.name}`")
        lines.extend(_finding_line(f, lang) for f in r.findings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def result_to_dict(result: LintResult, lang: str = "zh") -> dict[str, Any]:
    lang = normalize_lang(lang)
    data = result.to_dict()
    for item, f in zip(data["findings"], result.findings):
        item["message"] = finding_message(lang, f.kind, f.message_params)
    return data
