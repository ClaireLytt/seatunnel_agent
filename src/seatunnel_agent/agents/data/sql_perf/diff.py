"""Compare two EXPLAIN plans (before / after an optimization).

Findings are keyed by ``code|detail``: anything present only in the
before plan is *resolved*, only in the after plan is *introduced*,
and in both is *remaining*.  Scan rows are matched by table name so
pruning / pushdown / column-width changes show up side by side.
"""

from __future__ import annotations

from typing import Any

from .analyzer import PlanReport


def _keys(report: PlanReport) -> dict[str, dict[str, str]]:
    return {f"{f.code}|{f.detail}": f.to_dict() for f in report.findings}


def diff_plans(before: PlanReport, after: PlanReport) -> dict[str, Any]:
    """Structured delta between two analyzed plans."""
    old, new = _keys(before), _keys(after)
    resolved = [old[k] for k in old if k not in new]
    introduced = [new[k] for k in new if k not in old]
    remaining = [new[k] for k in new if k in old]

    old_scans = {s.table: s for s in before.scans}
    scan_changes: list[dict[str, Any]] = []
    for scan in after.scans:
        prev = old_scans.get(scan.table)
        if prev is None:
            continue
        changed = (prev.partition_filters != scan.partition_filters
                   or prev.pushed_filters != scan.pushed_filters
                   or prev.columns != scan.columns)
        if changed:
            scan_changes.append({"table": scan.table,
                                 "before": prev.to_dict(),
                                 "after": scan.to_dict()})
    return {
        "resolved": resolved,
        "introduced": introduced,
        "remaining": remaining,
        "scan_changes": scan_changes,
        "exchanges": {"before": before.exchanges, "after": after.exchanges},
        "joins": {"before": sum(before.joins.values()),
                  "after": sum(after.joins.values())},
    }


def render_diff(diff: dict[str, Any], lang: str = "zh") -> str:
    """Markdown section for a plan diff."""
    from seatunnel_agent.common.utils import normalize_lang

    from .i18n import tp

    lang = normalize_lang(lang)
    lines = [f"### {tp(lang, 'diff_title')}", "",
             tp(lang, "diff_stats").format(
                 resolved=len(diff["resolved"]),
                 introduced=len(diff["introduced"]),
                 remaining=len(diff["remaining"]),
                 ex_before=diff["exchanges"]["before"],
                 ex_after=diff["exchanges"]["after"],
                 j_before=diff["joins"]["before"],
                 j_after=diff["joins"]["after"]),
             ""]
    for key, items in (("diff_resolved", diff["resolved"]),
                       ("diff_introduced", diff["introduced"]),
                       ("diff_remaining", diff["remaining"])):
        if not items:
            continue
        lines.append(f"**{tp(lang, key)}**")
        lines.extend(f"- {f['code']} [{f['severity']}] `{f['detail']}`"
                     for f in items)
        lines.append("")
    if diff["scan_changes"]:
        from seatunnel_agent.common.utils import md_table

        lines.append(f"**{tp(lang, 'diff_scans')}**")

        def cell(s: dict[str, Any]) -> str:
            part = s["partition_filters"]
            pushed = s["pushed_filters"]
            empty = tp(lang, "empty_mark")

            def mark(v: str | None) -> str:
                if v is None:
                    return "-"
                return empty if v == "" else f"`{v[:40]}`"
            return (f"{tp(lang, 'rpt_col_part')}: {mark(part)} · "
                    f"{tp(lang, 'rpt_col_pushed')}: {mark(pushed)} · "
                    f"{s['columns']} {tp(lang, 'diff_cols')}")
        lines.extend(md_table(
            [tp(lang, "rpt_col_table"), tp(lang, "diff_col_before"),
             tp(lang, "diff_col_after")],
            [[f"`{row['table']}`", cell(row["before"]), cell(row["after"])]
             for row in diff["scan_changes"]]))
        lines.append("")
    if not (diff["resolved"] or diff["introduced"] or diff["remaining"]
            or diff["scan_changes"]):
        lines.append(tp(lang, "diff_no_change"))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
