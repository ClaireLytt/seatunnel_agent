"""Render a DiffResult as markdown."""

from __future__ import annotations

from seatunnel_agent.common.utils import md_table, normalize_lang

from .comparator import DiffResult
from .i18n import tp

__all__ = ["render_markdown"]

_TOP_MISMATCHES = 10


def render_markdown(result: DiffResult, lang: str = "zh") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}", "",
             tp(lang, "rpt_scope").format(
                 keys=", ".join(f"`{k}`" for k in result.keys),
                 tol=result.tolerance_pct, rt=result.rt_rows,
                 off=result.off_rows, matched=result.matched,
                 consistent=f"{result.consistent_pct:.1f}")
             + (tp(lang, "rpt_grace").format(
                 key=result.grace_key,
                 values=", ".join(f"`{v}`" for v in result.grace_excluded))
                if result.grace_excluded else ""), ""]
    clean = (not result.missing_in_rt and not result.missing_in_off
             and not result.mismatches)
    if result.missing_in_rt or result.missing_in_off:
        lines.append(f"### {tp(lang, 'rpt_missing')}")
        if result.missing_in_rt:
            lines.append(tp(lang, "missing_rt").format(
                n=len(result.missing_in_rt),
                examples=", ".join(f"`{k}`"
                                   for k in result.missing_in_rt[:5])))
        if result.missing_in_off:
            lines.append(tp(lang, "missing_off").format(
                n=len(result.missing_in_off),
                examples=", ".join(f"`{k}`"
                                   for k in result.missing_in_off[:5])))
        lines.append("")
    if result.mismatches:
        lines.append(f"### {tp(lang, 'rpt_mismatches')}".format(
            n=len(result.mismatches)))
        rows = []
        for m in result.mismatches[:_TOP_MISMATCHES]:
            diff = ("?" if m["diff_pct"] is None
                    else f"{m['diff_pct']:+g}")
            rows.append([f"`{m['key']}`", f"`{m['column']}`",
                         str(m["realtime"]), str(m["offline"]), diff])
        lines += md_table([tp(lang, "col_key"), tp(lang, "col_column"),
                           tp(lang, "col_rt"), tp(lang, "col_off"),
                           tp(lang, "col_diff")], rows)
        lines.append("")
    if result.biases:
        lines.append(f"### {tp(lang, 'rpt_biases')}")
        for b in result.biases:
            lines.append("- " + tp(lang, "bias_" + b.direction).format(
                **b.to_dict()))
        lines.append("")
    if clean:
        lines.append(tp(lang, "rpt_clean"))
    lines += ["", tp(lang, "rpt_disclaimer")]
    return "\n".join(lines)
