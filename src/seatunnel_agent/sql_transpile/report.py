# -*- coding: utf-8 -*-
"""Render TranspileResult / BatchResult as markdown or JSON-ready dicts."""

from __future__ import annotations

from typing import Any

from .i18n import issue_message, issue_suggestion, normalize_lang, tp
from .transpiler import BatchResult, Issue, TranspileResult

_LEVEL_MARK = {"error": "❌", "warn": "⚠️", "info": "ℹ️"}


def _issue_line(issue: Issue, lang: str) -> str:
    mark = _LEVEL_MARK.get(issue.level, "•")
    msg = issue_message(lang, issue.kind, issue.params)
    fix = issue_suggestion(lang, issue.kind)
    tail = f" — {fix}" if fix else ""
    return (f"- {mark} [{issue.level}] "
            f"{tp(lang, 'rpt_line')} {issue.line} · {msg}{tail}")


def render_markdown(result: TranspileResult, lang: str = "zh") -> str:
    """Full report: header, per-statement output, issue list, stats."""
    lang = normalize_lang(lang)
    c = result.counts()
    lines: list[str] = []
    head = (f"## {tp(lang, 'rpt_title')} "
            f"({result.src_dialect} → {result.dst_dialect})")
    if result.src_inferred:
        head += f"  \n*{tp(lang, 'rpt_src_inferred')} `{result.src_dialect}`*"
    lines.append(head)
    lines.append("")

    for s in result.statements:
        title = (f"### {tp(lang, 'rpt_stmt')} {s.index} "
                 f"({tp(lang, 'rpt_line')} {s.line})")
        lines.append(title)
        if s.ok:
            lines.append(f"```sql\n{s.output_sql.rstrip()}\n```")
        else:
            lines.append(f"*{tp(lang, 'rpt_parse_failed')}*")
            lines.append(f"```sql\n{s.source_sql.strip()}\n```")
        for issue in s.issues:
            lines.append(_issue_line(issue, lang))
        lines.append("")

    if not result.issues():
        lines.append(tp(lang, "rpt_no_issues"))
    lines.append("**" + tp(lang, "rpt_stats").format(**c) + "**")
    lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def render_batch_markdown(batch: BatchResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    c = batch.counts()
    src = batch.src_dialect or "auto"
    lines = [f"## {tp(lang, 'rpt_title')} ({src} → {batch.dst_dialect})", ""]
    lines.append(f"| {tp(lang, 'rpt_stmt')} | auto | manual | failed | → |")
    lines.append("|---|---|---|---|---|")
    for f in batch.files:
        fc = f.result.counts()
        out = f.out_path or "-"
        lines.append(
            f"| `{f.rel}` ({fc['total']}) | {fc['auto']} | {fc['manual']} "
            f"| {fc['failed']} | `{out}` |")
    lines.append("")
    for f in batch.files:
        for issue in f.result.issues():
            lines.append(f"- `{f.rel}` " + _issue_line(issue, lang)[2:])
    lines.append("")
    lines.append("**" + tp(lang, "rpt_batch_stats").format(**c) + "**")
    lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def result_to_dict(result: TranspileResult, lang: str = "zh") -> dict[str, Any]:
    """JSON payload: to_dict() plus rendered messages in the asked language."""
    lang = normalize_lang(lang)
    data = result.to_dict()
    for s_data, s in zip(data["statements"], result.statements):
        for i_data, issue in zip(s_data["issues"], s.issues):
            i_data["message"] = issue_message(lang, issue.kind, issue.params)
            i_data["suggestion"] = issue_suggestion(lang, issue.kind)
    return data


def batch_to_dict(batch: BatchResult, lang: str = "zh") -> dict[str, Any]:
    lang = normalize_lang(lang)
    data = batch.to_dict()
    for f_data, f in zip(data["files"], batch.files):
        for s_data, s in zip(f_data["statements"], f.result.statements):
            for i_data, issue in zip(s_data["issues"], s.issues):
                i_data["message"] = issue_message(
                    lang, issue.kind, issue.params)
                i_data["suggestion"] = issue_suggestion(lang, issue.kind)
    return data
