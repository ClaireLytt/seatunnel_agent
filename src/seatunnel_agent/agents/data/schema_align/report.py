"""Render an AlignResult as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import md_table, normalize_lang

from .aligner import AlignFinding, AlignResult
from .i18n import tp

__all__ = ["render_markdown"]


def _detail(f: AlignFinding, lang: str) -> str:
    try:
        return tp(lang, f.code).format(**f.detail)
    except (KeyError, IndexError, ValueError):
        return f"{tp(lang, f.code)} — {json.dumps(f.detail, ensure_ascii=False)}"


def render_markdown(result: AlignResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(src=result.source_table,
                                          dst=result.sink_table,
                                          matched=result.matched,
                                          n=len(result.findings)), ""]
    if result.findings:
        lines.append(f"### {tp(lang, 'rpt_findings')}")
        rows = [[f.code, tp(lang, "sev_" + f.severity), f"`{f.column}`",
                 _detail(f, lang), tp(lang, "rx_" + f.code)]
                for f in result.findings]
        lines += md_table([tp(lang, "col_code"), tp(lang, "col_sev"),
                           tp(lang, "col_column"), tp(lang, "col_detail"),
                           tp(lang, "col_rx")], rows)
    else:
        lines.append(tp(lang, "rpt_clean"))
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
