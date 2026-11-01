"""Render a DbDiagnosis as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import md_table, normalize_lang

from .diagnoser import DbDiagnosis, DbFinding
from .i18n import tp

__all__ = ["render_markdown"]


def _detail(f: DbFinding, lang: str) -> str:
    d = dict(f.detail)
    if f.code == "DB003":
        d["top"] = "; ".join(
            f"`{w['blocking']}`→`{w['waiting']}` {w['table']} "
            f"{w['seconds']:g}s" for w in d["top"])
    elif f.code == "DB005":
        d["top"] = "; ".join(
            f"`{q['sql'][:60]}` {q['duration_s']:g}s" for q in d["top"])
    try:
        return tp(lang, f.code).format(**d)
    except (KeyError, IndexError, ValueError):
        return f"{tp(lang, f.code)} — {json.dumps(f.detail, ensure_ascii=False)}"


def render_markdown(diag: DbDiagnosis, lang: str = "zh") -> str:
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
