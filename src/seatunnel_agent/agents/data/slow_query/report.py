"""Render a Diagnosis as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import fmt_bytes, fmt_secs, normalize_lang

from .diagnoser import Diagnosis
from .i18n import tp

__all__ = ["render_diff", "render_markdown"]


def render_diff(diff: dict, lang: str = "zh") -> str:
    """Markdown for an A/B run comparison (diagnoser.diff_runs)."""
    lang = normalize_lang(lang)
    t = diff["totals"]

    def fmt(key: str, value: float) -> str:
        return (fmt_bytes(value) if key.endswith("bytes")
                else fmt_secs(value))

    lines = [f"## {tp(lang, 'diff_title').format(a=diff['a'], b=diff['b'])}",
             "",
             f"| {tp(lang, 'diff_col_metric')} | A | B "
             f"| {tp(lang, 'diff_col_ratio')} |",
             "|---|---|---|---|"]
    for key, row in t.items():
        mark = "**" if row["ratio"] >= 2 else ""
        lines.append(f"| {tp(lang, 'diff_' + key)} "
                     f"| {fmt(key, row['a'])} | {fmt(key, row['b'])} "
                     f"| {mark}{row['ratio']:g}x{mark} |")
    if diff["stages"]:
        lines.append("")
        lines.append(f"### {tp(lang, 'diff_stages')}")
        lines.append(f"| stage | task max (A -> B) | task median (A -> B) "
                     f"| {tp(lang, 'diff_col_spill')} |")
        lines.append("|---|---|---|---|")
        for s in diff["stages"]:
            mx, md, sp = s["task_max_s"], s["task_median_s"], s["spill_bytes"]
            lines.append(
                f"| {s['stage']} "
                f"| {fmt_secs(mx['a'])} -> {fmt_secs(mx['b'])} "
                f"({mx['ratio']:g}x) "
                f"| {fmt_secs(md['a'])} -> {fmt_secs(md['b'])} "
                f"({md['ratio']:g}x) "
                f"| {fmt_bytes(sp['a'])} -> {fmt_bytes(sp['b'])} |")
    for key, names in (("diff_only_a", diff["only_a"]),
                       ("diff_only_b", diff["only_b"])):
        if names:
            lines.append("")
            lines.append(tp(lang, key) + " " +
                         ", ".join(f"`{n}`" for n in names))
    return "\n".join(lines)


def render_markdown(diag: Diagnosis, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    head = tp(lang, "rpt_run").format(name=diag.name,
                                      dur=fmt_secs(diag.duration_s))
    if diag.regression:
        head += tp(lang, "rpt_regression").format(
            reg=f"{diag.regression:g}",
            base=fmt_secs(diag.baseline_median_s))
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
