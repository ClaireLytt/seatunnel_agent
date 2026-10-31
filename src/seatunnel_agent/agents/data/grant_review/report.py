"""Render a ReviewResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .reviewer import ReviewResult

__all__ = ["render_markdown"]


def render_markdown(result: ReviewResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = {"approve": 0, "downgrade": 0, "reject": 0}
    for r in result.reviews:
        counts[r.decision] += 1
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(n=len(result.reviews),
                                          **counts), "",
             f"### {tp(lang, 'rpt_reviews')}"]
    rows = []
    for r in result.reviews:
        reasons = ", ".join(f"`{x}`" for x in r.reasons[:5]) or "-"
        downgrades = (", ".join(tp(lang, "dg_" + d) for d in r.downgrades)
                      or "-")
        rows.append([f"`{r.applicant}`", f"{r.risk:g}",
                     f"**{tp(lang, 'dec_' + r.decision)}**",
                     reasons, downgrades])
    lines += md_table([tp(lang, "col_applicant"), tp(lang, "col_risk"),
                       tp(lang, "col_decision"), tp(lang, "col_reasons"),
                       tp(lang, "col_downgrades")], rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
