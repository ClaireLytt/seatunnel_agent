"""Render a Diagnosis as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import (
    fmt_bytes,
    fmt_secs,
    md_table,
    normalize_lang,
)

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
             ""]

    def ratio_cell(ratio: float) -> str:
        return f"**{ratio:g}x**" if ratio >= 2 else f"{ratio:g}x"

    lines.extend(md_table(
        [tp(lang, "diff_col_metric"), "A", "B", tp(lang, "diff_col_ratio")],
        [[tp(lang, "diff_" + key), fmt(key, row["a"]), fmt(key, row["b"]),
          ratio_cell(row["ratio"])] for key, row in t.items()]))
    if diff["stages"]:
        lines.append("")
        lines.append(f"### {tp(lang, 'diff_stages')}")

        def move(pair: dict, fmt_one) -> str:
            return (f"{fmt_one(pair['a'])} -> {fmt_one(pair['b'])}"
                    + (f" ({pair['ratio']:g}x)" if "ratio" in pair else ""))

        lines.extend(md_table(
            ["stage", "task max (A -> B)", "task median (A -> B)",
             tp(lang, "diff_col_spill")],
            [[s["stage"], move(s["task_max_s"], fmt_secs),
              move(s["task_median_s"], fmt_secs),
              move(s["spill_bytes"], fmt_bytes)]
             for s in diff["stages"]]))
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
    if diag.stages:
        lines.append(f"### {tp(lang, 'rpt_stages')}")
        lines.extend(md_table(
            ["stage", "task max", "task median",
             tp(lang, "rpt_col_spill"), tp(lang, "rpt_col_input"),
             tp(lang, "rpt_col_tasks")],
            [[s["stage"], fmt_secs(s["task_max_s"]),
              fmt_secs(s["task_median_s"]), fmt_bytes(s["spill_bytes"]),
              fmt_bytes(s["input_bytes"]), str(s["tasks"])]
             for s in diag.stages]))
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
