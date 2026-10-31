"""Render a ConflictReport as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang

from .conflictor import ConflictReport
from .i18n import tp

__all__ = ["render_markdown", "render_place"]


def render_place(placement: dict, lang: str = "zh") -> str:
    """Markdown section for conflictor.place results."""
    lang = normalize_lang(lang)
    best, declared = placement["best"], placement["declared"]
    lines = ["### " + tp(lang, "plc_title").format(dag=placement["dag"]),
             "",
             tp(lang, "plc_best").format(
                 offset=f"{best['offset']:g}",
                 windows=best["windows"], writes=best["write_conflicts"],
                 peak=best["peak_slots"],
                 declared_offset=f"{declared['offset']:g}",
                 declared_windows=declared["windows"],
                 declared_writes=declared["write_conflicts"],
                 declared_peak=declared["peak_slots"])]
    key = (declared["windows"] + declared["write_conflicts"],
           declared["peak_slots"])
    best_key = (best["windows"] + best["write_conflicts"],
                best["peak_slots"])
    if key == best_key:
        lines.append("")
        lines.append(tp(lang, "plc_keep"))
    lines.append("")
    lines.append(f"**{tp(lang, 'plc_candidates')}**")
    lines.append(f"| {tp(lang, 'plc_col_offset')} "
                 f"| {tp(lang, 'plc_col_windows')} "
                 f"| {tp(lang, 'plc_col_writes')} "
                 f"| {tp(lang, 'plc_col_peak')} |")
    lines.append("|---|---|---|---|")
    for c in placement["candidates"]:
        mark = "**" if c is best else ""
        lines.append(f"| {mark}{c['offset']:g}{mark} | {c['windows']} "
                     f"| {c['write_conflicts']} | {c['peak_slots']} |")
    return "\n".join(lines)


def render_markdown(report: ConflictReport, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 cap_slots=report.cap_slots,
                 cap_mem=f"{report.cap_memory_gb:g}",
                 peak_slots=report.peak_slots,
                 peak_mem=f"{report.peak_memory_gb:g}",
                 windows=len(report.windows),
                 writes=len(report.write_conflicts)) + "**",
             ""]
    if report.suggestion:
        s = report.suggestion
        line = tp(lang, "rpt_suggestion").format(
            dag=s["dag"], delay=f"{s['delay']:g}",
            before=s["peak_slots_before"], after=s["peak_slots_after"],
            windows_after=s["windows_after"])
        if s.get("breaks_deadline"):
            bd = s["breaks_deadline"]
            line += tp(lang, "rpt_suggestion_breaks").format(
                dag=s["dag"], finish=f"{bd['finish']:g}",
                deadline=f"{bd['deadline']:g}")
        lines.append(line)
        lines.append("")
    if report.deadline_misses:
        lines.append(f"### {tp(lang, 'rpt_deadlines')}")
        for m in report.deadline_misses:
            lines.append("- " + tp(lang, "rpt_deadline_row").format(
                dag=m["dag"], finish=f"{m['finish']:g}",
                deadline=f"{m['deadline']:g}",
                late=f"{m['finish'] - m['deadline']:g}"))
        lines.append("")
    if report.windows:
        lines.append(f"### {tp(lang, 'rpt_windows')}")
        lines.append(f"| {tp(lang, 'rpt_col_window')} "
                     f"| {tp(lang, 'rpt_col_peak')} "
                     f"| {tp(lang, 'rpt_col_tasks')} |")
        lines.append("|---|---|---|")
        for w in report.windows:
            tasks = ", ".join(f"`{d}:{t}`" for d, t in w.tasks)
            lines.append(f"| {w.start:g} – {w.end:g} "
                         f"| {w.peak_slots} / {w.peak_memory_gb:g} "
                         f"| {tasks} |")
        lines.append("")
    if report.write_conflicts:
        lines.append(f"### {tp(lang, 'rpt_writes')}")
        for c in report.write_conflicts:
            lines.append(f"- `{c['table']}`: `{c['a']}` × `{c['b']}` "
                         f"({c['overlap'][0]:g} – {c['overlap'][1]:g})")
        lines.append("")
    if not report.windows and not report.write_conflicts:
        lines.append(tp(lang, "rpt_all_ok"))
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
