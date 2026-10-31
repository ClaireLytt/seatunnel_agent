"""Render a StormResult as markdown."""

from __future__ import annotations

import json

from seatunnel_agent.common.utils import md_table, normalize_lang

from .analyzer import AsFinding, StormResult
from .i18n import tp

__all__ = ["render_markdown"]

_TOP_CLUSTERS = 10


def _detail(f: AsFinding, lang: str) -> str:
    try:
        return tp(lang, f.code).format(**f.detail)
    except (KeyError, IndexError, ValueError):
        return f"{tp(lang, f.code)} — {json.dumps(f.detail, ensure_ascii=False)}"


def render_markdown(result: StormResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(total=result.total,
                                          distinct=len(result.clusters),
                                          ratio=f"{result.dedup_ratio:g}"),
             "", f"### {tp(lang, 'rpt_clusters')}"]
    rows = []
    for c in result.clusters[:_TOP_CLUSTERS]:
        rows.append([str(c.count), ", ".join(c.sources[:3]),
                     ", ".join(c.levels),
                     f"{c.first_ts[:16]} → {c.last_ts[:16]}",
                     f"`{c.sample_title[:70]}`"])
    lines += md_table([tp(lang, "col_count"), tp(lang, "col_sources"),
                       tp(lang, "col_levels"), tp(lang, "col_span"),
                       tp(lang, "col_sample")], rows)
    if result.findings:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        frows = [[f.code, tp(lang, "sev_" + f.severity), _detail(f, lang),
                  tp(lang, "rx_" + f.code)] for f in result.findings]
        lines += md_table([tp(lang, "col_code"), tp(lang, "col_sev"),
                           tp(lang, "col_detail"), tp(lang, "col_rx")],
                          frows)
    else:
        lines += ["", tp(lang, "rpt_no_findings")]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
