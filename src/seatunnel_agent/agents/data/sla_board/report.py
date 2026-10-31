"""Render an SlaBoard as markdown."""

from __future__ import annotations

from seatunnel_agent.common.severity import SEVERITY_MARK
from seatunnel_agent.common.utils import md_table, normalize_lang

from .board import SlaBoard
from .i18n import tp

__all__ = ["render_markdown"]


def render_markdown(board: SlaBoard, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    counts = board.counts()
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(tasks=len(board.tasks),
                                          runs=board.runs_total,
                                          rate=board.overall_rate,
                                          target=board.target,
                                          high=counts["high"],
                                          medium=counts["medium"]), "",
             f"### {tp(lang, 'rpt_board')}"]
    suffix = tp(lang, "min_suffix")
    rows = [[f"`{t.task}`", str(t.runs), f"{t.rate:.1%}",
             f"{t.p50_late_min:g} {suffix}" if t.misses else "-",
             f"{t.p90_late_min:g} {suffix}" if t.misses else "-",
             str(t.live_streak) if t.live_streak else "-"]
            for t in board.tasks]
    lines += md_table([tp(lang, "col_task"), tp(lang, "col_runs"),
                       tp(lang, "col_rate"), tp(lang, "col_p50"),
                       tp(lang, "col_p90"), tp(lang, "col_streak")], rows)
    if not board.findings:
        lines += ["", tp(lang, "rpt_clean")]
    else:
        lines += ["", f"### {tp(lang, 'rpt_findings')}"]
        rows = [[SEVERITY_MARK[f.severity], f.code, f"`{f.task}`",
                 tp(lang, f.code).format(value=f.value)]
                for f in board.findings]
        lines += md_table([tp(lang, "col_sev"), tp(lang, "col_code"),
                           tp(lang, "col_task"), tp(lang, "col_issue")],
                          rows)
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
