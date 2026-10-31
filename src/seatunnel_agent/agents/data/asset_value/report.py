"""Render a ValueResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .valuer import ValueResult

__all__ = ["render_markdown"]


def render_markdown(result: ValueResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(
                 today=result.today, n=len(result.assets),
                 median=f"{result.median_size_gb:g}",
                 core=result.tiers["core"], common=result.tiers["common"],
                 edge=result.tiers["edge"], idle=result.tiers["idle"]), "",
             f"### {tp(lang, 'rpt_assets')}"]
    rows = []
    for a in result.assets:
        ev = a.evidence
        days = ev.get("days_since_access")
        evidence = (f"{ev['access_cnt_30d']}×→{ev['access_pts']:g} / "
                    f"{ev['downstream_cnt']}↓→{ev['deps_pts']:g} / "
                    f"{days if days is not None else '?'}d→"
                    f"{ev['recency_pts']:g}")
        rows.append([f"`{a.table}`", f"{a.score:g}",
                     tp(lang, "tier_" + a.tier),
                     tp(lang, "q_" + a.quadrant),
                     f"{a.size_gb:g}", evidence])
    lines += md_table([tp(lang, "col_table"), tp(lang, "col_score"),
                       tp(lang, "col_tier"), tp(lang, "col_quadrant"),
                       tp(lang, "col_size"), tp(lang, "col_evidence")],
                      rows)
    lines += ["", tp(lang, "rpt_hint"), "", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
