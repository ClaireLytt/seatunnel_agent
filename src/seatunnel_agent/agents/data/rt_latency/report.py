"""Render a LatencyResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .analyzer import LatencyResult
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(result: LatencyResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    scope = tp(lang, "rpt_scope").format(events=result.events,
                                         dominant=result.dominant_hop
                                         or "-")
    if result.sla_ms > 0:
        scope += tp(lang, "rpt_sla").format(sla_ms=result.sla_ms,
                                            breaches=result.breaches)
    lines = [f"## {tp(lang, 'rpt_title')}", "", scope, "",
             f"### {tp(lang, 'rpt_stages')}"]
    rows = []
    stats = list(result.stages)
    if result.e2e:
        stats.append(result.e2e)
    for s in stats:
        bold = s.hop == result.dominant_hop
        hop = f"**`{s.hop}`**" if bold else f"`{s.hop}`"
        rows.append([hop, str(s.count), f"{s.p50_ms:g}", f"{s.p95_ms:g}",
                     f"{s.max_ms:g}"])
    lines += md_table([tp(lang, "col_hop"), tp(lang, "col_count"),
                       tp(lang, "col_p50"), tp(lang, "col_p95"),
                       tp(lang, "col_max")], rows)
    if result.outliers:
        lines += ["", f"### {tp(lang, 'rpt_outliers')}"]
        orows = [[f"`{o['event_id']}`", f"{o['e2e_ms']:g}",
                  f"`{o['worst_hop']}` {o['worst_ms']:g}ms"]
                 for o in result.outliers]
        lines += md_table([tp(lang, "col_event"), tp(lang, "col_e2e"),
                           tp(lang, "col_worst")], orows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
