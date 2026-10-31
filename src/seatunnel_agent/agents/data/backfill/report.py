"""Render a BackfillPlan as markdown or a JSON-ready dict."""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang

from .i18n import tp
from .planner import BackfillPlan, TablePlan, compact_ranges, plan_to_dict

__all__ = ["render_markdown", "plan_to_dict"]


def _kind(lang: str, t: TablePlan) -> str:
    if t.missing and t.cascade:
        return tp(lang, "kind_both")
    if t.missing:
        return tp(lang, "kind_missing")
    return tp(lang, "kind_cascade")


def render_markdown(result: BackfillPlan, lang: str = "zh",
                    cmd_template: str = "") -> str:
    lang = normalize_lang(lang)
    lines = [f"## {tp(lang, 'rpt_title')}",
             f"{tp(lang, 'rpt_now')} `{result.now.isoformat(sep=' ')}`",
             "",
             "**" + tp(lang, "rpt_stats").format(
                 tables=len(result.tables), batches=result.batches,
                 slots=result.total_slots,
                 skipped=len(result.skipped)) + "**",
             ""]
    if result.tables:
        lines.append(f"### {tp(lang, 'rpt_steps')}")
        lines.append(f"| {tp(lang, 'rpt_col_batch')} "
                     f"| {tp(lang, 'rpt_col_table')} "
                     f"| {tp(lang, 'rpt_col_kind')} "
                     f"| {tp(lang, 'rpt_col_dates')} "
                     f"| {tp(lang, 'rpt_col_from')} |")
        lines.append("|---|---|---|---|---|")
        for t in result.tables:
            name = f"`{t.table}`"
            if not t.in_inventory:
                name += tp(lang, "not_in_inventory")
            frm = (", ".join(f"`{u}`" for u in t.from_upstream)
                   if t.from_upstream else "-")
            lines.append(f"| {t.batch} | {name} | {_kind(lang, t)} "
                         f"| {compact_ranges(t.dates)} | {frm} |")
        lines.append("")
        if cmd_template.strip():
            lines.append(f"### {tp(lang, 'rpt_commands')}")
            lines.append("```bash")
            lines.extend(result.commands(cmd_template.strip()))
            lines.append("```")
            lines.append("")
    else:
        lines.append(tp(lang, "rpt_all_ok"))
        lines.append("")
    if result.skipped:
        lines.append(f"### {tp(lang, 'rpt_skipped')}")
        for table, reason in result.skipped:
            lines.append(f"- `{table}`: {tp(lang, 'skip_' + reason)}")
        lines.append("")
    if result.warnings:
        lines.append(f"### {tp(lang, 'rpt_warnings')}")
        lines.extend(f"- {w}" for w in result.warnings)
        lines.append("")
    lines.append(tp(lang, "rpt_disclaimer"))
    return "\n".join(lines)
