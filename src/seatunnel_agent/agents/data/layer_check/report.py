"""Render a LayerResult as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import md_table, normalize_lang

from .checker import LayerFinding, LayerResult
from .i18n import tp

__all__ = ["render_markdown"]


def _detail(f: LayerFinding, lang: str) -> str:
    d = dict(f.detail)
    if f.code == "LC004":
        d["tables"] = ", ".join(f"`{t}`" for t in d["tables"])
    try:
        return tp(lang, f.code).format(**d)
    except (KeyError, IndexError, ValueError):
        return f"{tp(lang, f.code)} — {json.dumps(f.detail, ensure_ascii=False)}"


def render_markdown(result: LayerResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    layers = " · ".join(f"{k}×{n}" for k, n in result.layer_counts.items())
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(tables=result.tables,
                                          edges=result.edges,
                                          layers=layers), ""]
    if result.findings:
        lines.append(f"### {tp(lang, 'rpt_findings')}")
        rows = [[f.code, tp(lang, "sev_" + f.severity), _detail(f, lang),
                 tp(lang, "rx_" + f.code)] for f in result.findings]
        lines += md_table([tp(lang, "col_code"), tp(lang, "col_sev"),
                           tp(lang, "col_detail"), tp(lang, "col_rx")],
                          rows)
    else:
        lines.append(tp(lang, "rpt_clean"))
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
