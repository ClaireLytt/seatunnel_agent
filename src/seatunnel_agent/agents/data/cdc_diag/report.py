"""Render a CdcDiagnosis as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import md_table, normalize_lang

from .diagnoser import CdcDiagnosis, CdcFinding
from .i18n import tp

__all__ = ["render_markdown"]


def _detail(f: CdcFinding, lang: str) -> str:
    d = dict(f.detail)
    if f.code == "CD005":
        d["classes"] = "; ".join(
            f"{k}×{len(v)} (`{v[0]}`)" for k, v in d["classes"].items())
    try:
        return tp(lang, f.code).format(**d)
    except (KeyError, IndexError, ValueError):
        return f"{tp(lang, f.code)} — {json.dumps(f.detail, ensure_ascii=False)}"


def render_markdown(diag: CdcDiagnosis, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    sections = ", ".join(f"`{s}`" for s in diag.sections_seen) or "-"
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(sections=sections,
                                          n=len(diag.findings)), ""]
    if diag.findings:
        lines.append(f"### {tp(lang, 'rpt_findings')}")
        rows = [[f.code, tp(lang, "sev_" + f.severity), _detail(f, lang),
                 tp(lang, "rx_" + f.code)] for f in diag.findings]
        lines += md_table([tp(lang, "col_code"), tp(lang, "col_sev"),
                           tp(lang, "col_detail"), tp(lang, "col_rx")],
                          rows)
    else:
        lines.append(tp(lang, "rpt_clean"))
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
