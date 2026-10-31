"""Render a DriftResult as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import md_table, normalize_lang

from .comparator import DriftFinding, DriftResult
from .i18n import tp

__all__ = ["render_markdown"]


def _finding_cell(f: DriftFinding, lang: str) -> str:
    d = dict(f.detail)
    if f.code == "DA001":
        d["change"] = tp(lang, "change_" + d["change"])
    elif f.code == "DA004":
        d["moved"] = "; ".join(
            f"`{m['value']}` {m['from_pct']}%→{m['to_pct']}%"
            for m in d["moved"])
    elif f.code == "DA005":
        d["appeared"] = ", ".join(f"`{v}`" for v in d["appeared"]) or "-"
        d["vanished"] = ", ".join(f"`{v}`" for v in d["vanished"]) or "-"
    try:
        return tp(lang, f.code).format(**d)
    except (KeyError, IndexError, ValueError):  # evidence shape drifted
        return f"{tp(lang, f.code)} — {json.dumps(f.detail, ensure_ascii=False)}"


def render_markdown(result: DriftResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(base=result.baseline_rows,
                                          cur=result.current_rows,
                                          cols=result.columns_compared), ""]
    if result.findings:
        lines.append(f"### {tp(lang, 'rpt_findings')}".format(
            n=len(result.findings)))
        rows = [[f.code, tp(lang, "sev_" + f.severity), f"`{f.column}`",
                 _finding_cell(f, lang)] for f in result.findings]
        lines += md_table([tp(lang, "col_code"), tp(lang, "col_sev"),
                           tp(lang, "col_col"), tp(lang, "col_detail")],
                          rows)
    else:
        lines.append(tp(lang, "rpt_no_findings"))
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
