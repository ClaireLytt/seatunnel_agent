"""Render a PartitionHealthResult as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import md_table, normalize_lang

from .analyzer import PartitionHealthResult, PhFinding
from .i18n import tp

__all__ = ["render_markdown"]


def _detail(f: PhFinding, lang: str) -> str:
    d = dict(f.detail)
    if f.code == "PH001":
        d["gaps"] = ", ".join(d["gaps"])
    elif f.code == "PH002":
        d["partitions"] = ", ".join(f"`{p}`" for p in d["partitions"])
    try:
        return tp(lang, f.code).format(**d)
    except (KeyError, IndexError, ValueError):
        return f"{tp(lang, f.code)} — {json.dumps(f.detail, ensure_ascii=False)}"


def render_markdown(result: PartitionHealthResult,
                    lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(tables=result.tables,
                                          partitions=result.partitions),
             ""]
    if result.findings:
        lines.append(f"### {tp(lang, 'rpt_findings')}")
        rows = [[f.code, tp(lang, "sev_" + f.severity), f"`{f.table}`",
                 _detail(f, lang), tp(lang, "rx_" + f.code)]
                for f in result.findings]
        lines += md_table([tp(lang, "col_code"), tp(lang, "col_sev"),
                           tp(lang, "col_table"), tp(lang, "col_detail"),
                           tp(lang, "col_rx")], rows)
    else:
        lines.append(tp(lang, "rpt_clean"))
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
