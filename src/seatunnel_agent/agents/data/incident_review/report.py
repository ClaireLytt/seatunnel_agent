"""Render an IncidentReview as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .i18n import tp
from .reviewer import IncidentReview

__all__ = ["render_markdown"]


def _fmt(value: float | None, lang: str) -> str:
    if value is None:
        return tp(lang, "na")
    return f"{value:g}{tp(lang, 'min_suffix')}"


def render_markdown(review: IncidentReview, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(events=len(review.events),
                                          mttd=_fmt(review.mttd_min, lang),
                                          mtta=_fmt(review.mtta_min, lang),
                                          mttr=_fmt(review.mttr_min, lang)),
             "", f"### {tp(lang, 'rpt_timeline')}"]
    rows = [[f"{e.minute:g}", tp(lang, "kind_" + e.kind), e.text or "-"]
            for e in review.events]
    lines += md_table([tp(lang, "col_minute"), tp(lang, "col_kind"),
                       tp(lang, "col_text")], rows)
    if not review.findings:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code,
                 tp(lang, f.code).format(value=f.value,
                                         detail=f.detail or "-")]
                for f in review.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_issue")], rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
