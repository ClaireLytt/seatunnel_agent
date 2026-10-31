"""Render a VolResult as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import md_table, normalize_lang

from .analyzer import _MAD_K, _WINDOW, VolFinding, VolResult
from .i18n import tp

__all__ = ["render_markdown"]


def _finding_cell(f: VolFinding, lang: str) -> str:
    d = dict(f.detail)
    if f.code == "VA005":
        d["gaps"] = ", ".join(d["gaps"])
    try:
        return tp(lang, f.code).format(**d)
    except (KeyError, IndexError, ValueError):  # evidence shape drifted
        return f"{tp(lang, f.code)} — {json.dumps(f.detail, ensure_ascii=False)}"


def render_markdown(result: VolResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    detail = ", ".join(f"`{m}`×{n}" for m, n in result.metrics.items())
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(metrics=len(result.metrics),
                                          detail=detail), ""]
    if result.findings:
        lines.append(f"### {tp(lang, 'rpt_findings')}".format(
            n=len(result.findings)))
        rows = [[f.code, tp(lang, "sev_" + f.severity), f"`{f.metric}`",
                 _finding_cell(f, lang)] for f in result.findings]
        lines += md_table([tp(lang, "col_code"), tp(lang, "col_sev"),
                           tp(lang, "col_metric"), tp(lang, "col_detail")],
                          rows)
        lines += ["", tp(lang, "rpt_prescription")]
    else:
        lines.append(tp(lang, "rpt_no_findings"))
    lines += ["", tp(lang, "rpt_disclaimer").format(window=_WINDOW,
                                                    k=f"{_MAD_K:g}")]
    return "\n".join(lines)
