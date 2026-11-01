"""Render a ProfileResult as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .profiler import ColumnProfile, Finding, ProfileResult

__all__ = ["render_markdown"]


def _range_cell(c: ColumnProfile) -> str:
    if c.vmin is not None:
        return f"{c.vmin:g} … {c.vmax:g} (mean {c.mean:.4g})"
    return ", ".join(f"`{v}`×{n}" for v, n in c.top[:3]) or "-"


def _finding_cell(f: Finding, lang: str) -> str:
    d = dict(f.detail)
    if f.code == "SP001":
        d["buckets"] = ", ".join(f"{b}:{n}" for b, n in d["buckets"].items())
    elif f.code == "SP003":
        d = {"detail": d.get("value", d.get("reason", "-"))}
    elif f.code == "SP004":
        d["minority"] = ", ".join(f"{b}:{n}" for b, n in d["minority"].items())
        d["examples"] = "; ".join(
            f"row {e['row']}: `{e['value']}`" for e in d["examples"]) or "-"
    elif f.code == "SP005":
        d["examples"] = ", ".join(f"`{v}`" for v in d["examples"])
    elif f.code == "SP006":
        d["variants"] = "; ".join(
            " / ".join(f"`{v}`" for v in vs) for vs in d["variants"].values())
    try:
        return tp(lang, f.code).format(**d)
    except (KeyError, IndexError):  # defensive: evidence shape drifted
        return f"{tp(lang, f.code)} — {json.dumps(f.detail, ensure_ascii=False)}"


def render_markdown(result: ProfileResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(sampled=result.sampled_rows,
                                          total=result.total_rows,
                                          cols=len(result.columns)), ""]
    lines.append(f"### {tp(lang, 'rpt_columns')}")
    rows = []
    for c in result.columns:
        rows.append([f"`{c.name}`", c.kind, f"{c.null_pct:.1f}",
                     f"{c.unique_pct:.1f}", _range_cell(c)])
    lines += md_table([tp(lang, "col_name"), tp(lang, "col_kind"),
                       tp(lang, "col_null"), tp(lang, "col_unique"),
                       tp(lang, "col_range")], rows)
    lines.append("")
    if result.findings:
        lines.append(f"### {tp(lang, 'rpt_findings')}".format(
            n=len(result.findings)))
        frows = [[f.code, tp(lang, "sev_" + f.severity), f"`{f.column}`",
                  _finding_cell(f, lang)] for f in result.findings]
        lines += md_table([tp(lang, "col_code"), tp(lang, "col_sev"),
                           tp(lang, "col_col"), tp(lang, "col_detail")],
                          frows)
    else:
        lines.append(tp(lang, "rpt_no_findings"))
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
