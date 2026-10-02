# -*- coding: utf-8 -*-
"""Render FmtResult(s) as markdown or JSON-ready dicts."""

from __future__ import annotations

from typing import Any, Iterable

from .formatter import FmtFileResult, FmtResult
from .i18n import normalize_lang, tp


def render_markdown(result: FmtResult, lang: str = "zh",
                    show_diff: bool = True) -> str:
    lang = normalize_lang(lang)
    lines = [f"## 🪄 {tp(lang, 'rpt_title')}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 statements=result.statements, failed=result.failed) + "**",
             ""]
    if result.select_star:
        lines.append("- ⚠️ " + tp(lang, "rpt_select_star").format(
            n=result.select_star))
        lines.append("")
    if result.parse_errors:
        lines.append(f"### ⛔ {tp(lang, 'rpt_errors')}")
        lines.extend(f"- {e}" for e in result.parse_errors)
        lines.append("")
    if not result.changed:
        lines.append("✅ " + tp(lang, "rpt_unchanged"))
    else:
        lines.append(f"### {tp(lang, 'rpt_formatted')}")
        lines.append("```sql\n" + result.formatted.rstrip() + "\n```")
        if show_diff:
            lines.append(f"<details><summary>{tp(lang, 'rpt_diff')}"
                         "</summary>\n")
            lines.append("```diff\n" + result.diff().rstrip()
                         + "\n```\n</details>")
    lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def render_batch_markdown(results: Iterable[FmtFileResult],
                          lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    results = list(results)
    changed = sum(1 for r in results if r.result.changed)
    written = sum(1 for r in results if r.written)
    failed = sum(r.result.failed for r in results)
    lines = [f"## 🪄 {tp(lang, 'rpt_title')}", "",
             "**" + tp(lang, "rpt_batch_stats").format(
                 files=len(results), changed=changed, written=written,
                 failed=failed) + "**", ""]
    lines.append("| | file | statements | SELECT * |")
    lines.append("|---|---|---|---|")
    for r in results:
        if r.result.failed:
            mark = "⛔"
        elif r.written:
            mark = "✍️ " + tp(lang, "rpt_written")
        elif r.result.changed:
            mark = "⚠️ " + tp(lang, "rpt_changed")
        else:
            mark = "✅ " + tp(lang, "rpt_clean")
        lines.append(f"| {mark} | `{r.path}` | {r.result.statements} "
                     f"| {r.result.select_star or '-'} |")
    lines.append("")
    for r in results:
        if r.result.parse_errors:
            lines.append(f"### ⛔ `{r.path}`")
            lines.extend(f"- {e}" for e in r.result.parse_errors)
            lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def result_to_dict(result: FmtResult) -> dict[str, Any]:
    return result.to_dict()
