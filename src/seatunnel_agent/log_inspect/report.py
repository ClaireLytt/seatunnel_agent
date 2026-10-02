# -*- coding: utf-8 -*-
"""Render InspectReport as markdown or a JSON-ready dict."""

from __future__ import annotations

from typing import Any

from .clusterer import InspectReport, LogCluster
from .i18n import normalize_lang, tp

_LEVEL_MARK = {"error": "⛔", "warn": "⚠️"}


def _head(cluster: LogCluster) -> str:
    return cluster.exception or cluster.template or "(no message)"


def render_markdown(report: InspectReport, lang: str = "zh",
                    top: int = 10) -> str:
    lang = normalize_lang(lang)
    c = report.counts()
    lines = [f"## 🧾 {tp(lang, 'rpt_title')}",
             f"{tp(lang, 'rpt_root')} `{report.root}`",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 files=report.files_scanned, lines=report.lines_scanned,
                 events=c["events"], clusters=c["clusters"],
                 error=c["error"], warn=c["warn"]) + "**",
             ""]
    if not report.clusters:
        lines.append(tp(lang, "rpt_clean"))
    else:
        shown = report.clusters[:top]
        lines.append(f"### {tp(lang, 'rpt_top')}")
        lines.append(
            f"| # | {tp(lang, 'rpt_col_level')} "
            f"| {tp(lang, 'rpt_col_exception')} "
            f"| {tp(lang, 'rpt_col_count')} | {tp(lang, 'rpt_col_files')} "
            f"| {tp(lang, 'rpt_col_first')} | {tp(lang, 'rpt_col_last')} |")
        lines.append("|---|---|---|---|---|---|---|")
        for i, cl in enumerate(shown, start=1):
            mark = _LEVEL_MARK.get(cl.level, "•")
            lines.append(
                f"| {i} | {mark} {cl.level} | `{_head(cl)}` | {cl.count} "
                f"| {len(cl.files)} | {cl.first_ts or '-'} "
                f"| {cl.last_ts or '-'} |")
        lines.append("")
        for i, cl in enumerate(shown, start=1):
            mark = _LEVEL_MARK.get(cl.level, "•")
            lines.append(f"### {mark} {tp(lang, 'rpt_cluster')} {i}: "
                         f"`{_head(cl)}` ×{cl.count}")
            if cl.template and cl.exception:
                lines.append(f"- {tp(lang, 'rpt_template')}: `{cl.template}`")
            if cl.top_frame:
                lines.append(f"- {tp(lang, 'rpt_top_frame')}: "
                             f"`{cl.top_frame}`")
            files = " · ".join(
                f"`{path}`×{n}" for path, n in
                sorted(cl.files.items(), key=lambda kv: -kv[1])[:5])
            lines.append(f"- {tp(lang, 'rpt_files')}: {files}")
            if cl.sample:
                lines.append(f"- {tp(lang, 'rpt_sample')}:")
                lines.append("```text\n" + cl.sample + "\n```")
            lines.append("")
    if report.warnings:
        lines.append(f"### ⚠️ {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in report.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def report_to_dict(report: InspectReport, top: int | None = None,
                   ) -> dict[str, Any]:
    data = report.to_dict()
    if top is not None:
        data["clusters"] = data["clusters"][:top]
    return data
