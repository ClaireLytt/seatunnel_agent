"""Render an AttributionResult as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import md_table, normalize_lang

from .attributor import AttributionResult, MaFinding
from .i18n import tp

__all__ = ["render_markdown"]

_TOP_MOVERS = 8


def _detail(f: MaFinding, lang: str) -> str:
    d = dict(f.detail)
    if f.code == "MA001":
        d["direction"] = tp(lang, "dir_" + d["direction"])
    try:
        return tp(lang, f.code).format(**d)
    except (KeyError, IndexError, ValueError):
        return f"{tp(lang, f.code)} — {json.dumps(f.detail, ensure_ascii=False)}"


def render_markdown(result: AttributionResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    pct = (tp(lang, "rpt_pct").format(p=result.delta_pct)
           if result.delta_pct is not None else "")
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(metric=result.metric,
                                          base=result.total_base,
                                          cur=result.total_cur,
                                          delta=result.delta, pct=pct), ""]
    if result.delta == 0 and not result.findings:
        lines.append(tp(lang, "rpt_flat"))
    if result.findings:
        lines.append(f"### {tp(lang, 'rpt_findings')}")
        rows = [[f.code, tp(lang, "sev_" + f.severity), _detail(f, lang)]
                for f in result.findings]
        lines += md_table([tp(lang, "col_code"), tp(lang, "col_sev"),
                           tp(lang, "col_detail")], rows)
    for b in result.breakdowns:
        lines += ["", "### " + tp(lang, "rpt_dim").format(dim=b.dimension)]
        rows = []
        for m in b.movers[:_TOP_MOVERS]:
            share = (f"{m['share_pct']:g}%" if m["share_pct"] is not None
                     else "-")
            rows.append([f"`{m['value']}`", f"{m['baseline']:g}",
                         f"{m['current']:g}", f"{m['contribution']:+g}",
                         share, tp(lang, "status_" + m["status"])])
        lines += md_table([tp(lang, "col_value"), tp(lang, "col_base"),
                           tp(lang, "col_cur"), tp(lang, "col_contrib"),
                           tp(lang, "col_share"), tp(lang, "col_status")],
                          rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
