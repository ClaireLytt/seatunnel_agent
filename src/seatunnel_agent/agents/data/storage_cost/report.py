"""Render a CostResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .analyzer import CostAction, CostResult
from .i18n import tp

__all__ = ["render_markdown"]


def _detail(a: CostAction, lang: str) -> str:
    d = a.detail
    if a.kind == "cold_tier":
        days = d.get("days_since_access")
        if days is None:
            return tp(lang, "d_cold_nodate").format(
                deps=d.get("downstream_cnt", 0))
        return tp(lang, "d_cold").format(days=days,
                                         deps=d.get("downstream_cnt", 0))
    if a.kind == "drop_partitions":
        return tp(lang, "d_drop").format(count=d["expired_partitions"],
                                         retention=d["retention_days"],
                                         oldest=d["oldest"])
    return tp(lang, "d_compact").format(avg=f"{d['avg_file_mb']:g}",
                                        threshold=f"{d['threshold_mb']:g}")


def render_markdown(result: CostResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(today=result.today,
                                          total=f"{result.total_gb:g}",
                                          reclaim=f"{result.reclaimable_gb:g}",
                                          n=len(result.actions)), ""]
    if result.actions:
        lines.append(f"### {tp(lang, 'rpt_actions')}")
        rows = [[tp(lang, "kind_" + a.kind), f"`{a.table}`",
                 f"{a.freed_gb:g}", tp(lang, "sev_" + a.severity),
                 _detail(a, lang)] for a in result.actions]
        lines += md_table([tp(lang, "col_kind"), tp(lang, "col_table"),
                           tp(lang, "col_freed"), tp(lang, "col_sev"),
                           tp(lang, "col_detail")], rows)
    else:
        lines.append(tp(lang, "rpt_clean"))
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
