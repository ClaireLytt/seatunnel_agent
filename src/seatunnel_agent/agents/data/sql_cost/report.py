"""Render a CostCard as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import (
    fmt_bytes,
    fmt_secs,
    md_table,
    normalize_lang,
)

from .estimator import CostCard
from .i18n import tp

__all__ = ["render_batch", "render_calibration", "render_compare",
           "render_markdown", "render_what_if"]


def render_markdown(card: CostCard, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 scan=fmt_bytes(card.scan_bytes),
                 shuffle=fmt_bytes(card.shuffle_bytes),
                 rows=f"{card.output_rows:,.0f}",
                 core_s=f"{card.core_seconds:,.0f}") + "**",
             "",
             tp(lang, "rpt_verdict").format(
                 par=card.parallelism,
                 lo=fmt_secs(card.wall_seconds[0]),
                 hi=fmt_secs(card.wall_seconds[1]),
                 mem=fmt_bytes(card.memory_peak_bytes)),
             ""]
    if card.scans:
        lines.append(f"### {tp(lang, 'rpt_scans')}")
        lines.append(f"| {tp(lang, 'rpt_col_table')} "
                     f"| {tp(lang, 'rpt_col_bytes')} "
                     f"| {tp(lang, 'rpt_col_rows')} "
                     f"| {tp(lang, 'rpt_col_pruned')} "
                     f"| {tp(lang, 'rpt_col_colratio')} |")
        lines.append("|---|---|---|---|---|")
        for s in card.scans:
            pruned = (tp(lang, "yes") if s.pruned
                      else f"**{tp(lang, 'no')}**")
            lines.append(f"| `{s.table}` | {fmt_bytes(s.bytes)} "
                         f"| {s.rows:,.0f} | {pruned} "
                         f"| {s.col_ratio:.0%} |")
        lines.append("")
    if card.missing:
        lines.append(f"### {tp(lang, 'rpt_missing')}")
        lines.append(", ".join(f"`{t}`" for t in card.missing))
        lines.append("")
    lines.append(f"### {tp(lang, 'rpt_assumptions')}")
    lines.append(tp(lang, "asm_lines"))
    lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)


def render_what_if(whatif: dict, lang: str = "zh") -> str:
    """Markdown section for a what-if delta from estimator.what_if."""
    lang = normalize_lang(lang)
    lines = [f"### {tp(lang, 'wi_title')}"]
    lines += [f"- `{s}`" for s in whatif["assumed"]]
    before = whatif["base_scan_bytes"]
    lines.append("")
    lines.append(tp(lang, "wi_scan").format(
        before=fmt_bytes(before), after=fmt_bytes(whatif["scan_bytes"]),
        pct=f"{whatif['scan_saved_pct']:g}"))
    if whatif["scan_saved_pct"] <= 0:
        lines.append("")
        lines.append(tp(lang, "wi_no_save"))
    return "\n".join(lines)


def render_compare(cmp: dict, lang: str = "zh") -> str:
    """Markdown section for an original-vs-rewrite delta (estimator.compare)."""
    lang = normalize_lang(lang)
    base, rewrite, saved = cmp["base"], cmp["rewrite"], cmp["saved_pct"]
    rows = [
        ("cmp_scan", fmt_bytes(base["scan_bytes"]),
         fmt_bytes(rewrite["scan_bytes"]), saved["scan"]),
        ("cmp_shuffle", fmt_bytes(base["shuffle_bytes"]),
         fmt_bytes(rewrite["shuffle_bytes"]), saved["shuffle"]),
        ("cmp_memory", fmt_bytes(base["memory_peak_bytes"]),
         fmt_bytes(rewrite["memory_peak_bytes"]), saved["memory"]),
        ("cmp_core", f"{base['core_seconds']:,.0f}",
         f"{rewrite['core_seconds']:,.0f}", saved["core_seconds"]),
    ]
    lines = [f"### {tp(lang, 'cmp_title')}"]
    lines.extend(md_table(
        [tp(lang, "cmp_col_axis"), tp(lang, "cmp_col_base"),
         tp(lang, "cmp_col_rewrite"), tp(lang, "cmp_col_saved")],
        [[tp(lang, key), before, after,
          f"**{pct:g}%**" if pct > 0 else f"{pct:g}%"]
         for key, before, after, pct in rows]))
    if any(v < 0 for v in saved.values()):
        lines.append("")
        lines.append(tp(lang, "cmp_worse"))
    return "\n".join(lines)


def render_calibration(cal: dict, lang: str = "zh") -> str:
    """Markdown for estimator.calibrate output."""
    lang = normalize_lang(lang)
    rows = []
    dur = cal["duration"]
    rows.append([tp(lang, "cal_duration"),
                 fmt_secs(dur["estimated"]), fmt_secs(dur["actual"]),
                 f"{dur['ratio']:g}x"])
    for key in ("scan_bytes", "shuffle_bytes"):
        if key in cal:
            rows.append([tp(lang, "cal_" + key),
                         fmt_bytes(cal[key]["estimated"]),
                         fmt_bytes(cal[key]["actual"]),
                         f"{cal[key]['ratio']:g}x"])
    lines = [f"### {tp(lang, 'cal_title')}"]
    lines.extend(md_table(
        [tp(lang, "cal_col_axis"), tp(lang, "cal_col_est"),
         tp(lang, "cal_col_act"), tp(lang, "cal_col_ratio")], rows))
    lines.append("")
    if dur["in_band"]:
        lines.append(tp(lang, "cal_in_band"))
    else:
        lines.append(tp(lang, "cal_off_band").format(
            lo=fmt_secs(dur["band"][0]), hi=fmt_secs(dur["band"][1])))
    return "\n".join(lines)


def render_batch(batch: dict, lang: str = "zh") -> str:
    """Markdown for a workload ranking (estimator.estimate_batch)."""
    lang = normalize_lang(lang)
    rows = [[q["name"], fmt_bytes(q["scan_bytes"]),
             fmt_bytes(q["shuffle_bytes"]), f"{q['core_seconds']:,.0f}"]
            for q in batch["queries"]]
    totals = batch["totals"]
    rows.append([
        "**" + tp(lang, "bat_total").format(n=len(batch["queries"])) + "**",
        f"**{fmt_bytes(totals['scan_bytes'])}**",
        f"**{fmt_bytes(totals['shuffle_bytes'])}**",
        f"**{totals['core_seconds']:,.0f}**"])
    lines = [f"### {tp(lang, 'bat_title')}"]
    lines.extend(md_table(
        [tp(lang, "bat_col_query"), tp(lang, "bat_col_scan"),
         tp(lang, "bat_col_shuffle"), tp(lang, "bat_col_core")], rows))
    if batch["skipped"]:
        lines.append("")
        lines.append(tp(lang, "bat_skipped") + " "
                     + ", ".join(f"`{s}`" for s in batch["skipped"]))
    return "\n".join(lines)
