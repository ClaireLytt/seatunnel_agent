"""Render a ScheduleResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .advisor import ScheduleResult
from .i18n import tp

__all__ = ["render_markdown"]

_THIN_MARGIN_MIN = 30.0


def render_markdown(result: ScheduleResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    margin = ""
    if result.margin_min is not None:
        key = ("rpt_margin_neg" if result.margin_min < 0
               else "rpt_margin_thin" if result.margin_min < _THIN_MARGIN_MIN
               else "rpt_margin_ok")
        margin = tp(lang, key).format(m=result.margin_min)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(day_start=result.day_start,
                                          sla_task=result.sla_task,
                                          deadline=result.deadline,
                                          finish=result.finish,
                                          margin=margin), "",
             tp(lang, "rpt_critical").format(
                 path=" → ".join(f"`{t}`" for t in result.critical_path)),
             "",
             tp(lang, "rpt_peak").format(n=result.peak_parallelism,
                                         at=result.peak_window), "",
             f"### {tp(lang, 'rpt_tasks')}"]
    rows = []
    for s in result.tasks:
        d = s.to_dict()
        rows.append([f"`{s.name}`",
                     f"{d['start']} → {d['finish']}",
                     f"{s.duration_min:g}",
                     "-" if s.slack_min is None else f"{s.slack_min:g}",
                     tp(lang, "yes") if s.critical else "-"])
    lines += md_table([tp(lang, "col_task"), tp(lang, "col_window"),
                       tp(lang, "col_duration"), tp(lang, "col_slack"),
                       tp(lang, "col_critical")], rows)
    if result.movable:
        lines += ["", f"### {tp(lang, 'rpt_movable')}"]
        lines += [tp(lang, "movable_line").format(**m)
                  for m in result.movable]
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
