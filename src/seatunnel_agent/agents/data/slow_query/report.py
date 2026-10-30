"""Render a Diagnosis as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang

from .diagnoser import Diagnosis
from .i18n import tp

__all__ = ["render_markdown"]


def _secs(s: float) -> str:
    if s < 90:
        return f"{s:.0f}s"
    if s < 5400:
        return f"{s / 60:.1f}min"
    return f"{s / 3600:.1f}h"


def render_markdown(diag: Diagnosis, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    head = tp(lang, "rpt_run").format(name=diag.name,
                                      dur=_secs(diag.duration_s))
    if diag.regression:
        head += tp(lang, "rpt_regression").format(
            reg=f"{diag.regression:g}",
            base=_secs(diag.baseline_median_s))
    lines = [f"## {tp(lang, 'rpt_title')}", "", head, ""]
    if diag.causes:
        lines.append(f"### {tp(lang, 'rpt_causes')}")
        lines.append(f"| {tp(lang, 'rpt_col_code')} "
                     f"| {tp(lang, 'rpt_col_share')} "
                     f"| {tp(lang, 'rpt_col_detail')} "
                     f"| {tp(lang, 'rpt_col_rx')} |")
        lines.append("|---|---|---|---|")
        for c in diag.causes:
            lines.append(f"| {c.code} | {c.share:.0%} | `{c.detail}` "
                         f"| {tp(lang, c.code)} |")
        lines.append("")
    else:
        lines.append(tp(lang, "rpt_none"))
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
