"""Scan-savings ROI for the advisor's partition picks.

Reuses the sql_cost estimator: every workload statement is estimated
against the declared stats inventory twice — as-is, and with the
recommended partition column assumed on its table — and the scan
deltas are summed.  The result ranks the partition recommendations by
how many bytes they would actually save for *this* workload, instead
of by filter frequency alone.

Tables missing from the inventory, tables whose declared partition
count is < 2 (nothing to prune into) and statements the estimator
cannot parse are skipped and counted, never guessed.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from seatunnel_agent.agents.data.sql_cost import TableStats, estimate

from .advisor import WorkloadAdvice, _split


def partition_roi(advice: WorkloadAdvice, workload: str,
                  stats: dict[str, TableStats]) -> dict[str, Any]:
    """Per-table scan savings of the recommended partitioning."""
    # the baseline costs do not depend on the assumed table — estimate
    # each statement once up front instead of once per recommendation
    bases: list[tuple[str, float]] = []
    for stmt in _split(workload):
        try:
            bases.append((stmt, estimate(stmt, stats).scan_bytes))
        except ValueError:
            continue
    rows: list[dict[str, Any]] = []
    skipped_tables: list[str] = []
    for t in advice.tables:
        if not t.partition_col:
            continue
        st = stats.get(t.table)
        if st is None or st.partitions < 2:
            skipped_tables.append(t.table)
            continue
        if st.partition_col == t.partition_col:
            continue  # already partitioned as recommended
        tweaked = dict(stats)
        tweaked[t.table] = dataclasses.replace(
            st, partition_col=t.partition_col)
        saved = 0.0
        base_total = 0.0
        estimated = 0
        for stmt, base_scan in bases:
            try:
                after = estimate(stmt, tweaked)
            except ValueError:
                continue
            estimated += 1
            base_total += base_scan
            saved += base_scan - after.scan_bytes
        rows.append({
            "table": t.table, "partition_col": t.partition_col,
            "saved_bytes": round(saved),
            "saved_pct": (round(100 * saved / base_total, 1)
                          if base_total else 0.0),
            "statements_estimated": estimated,
        })
    rows.sort(key=lambda r: (-r["saved_bytes"], r["table"]))
    return {"rows": rows, "skipped_tables": sorted(skipped_tables)}


def render_roi(roi: dict[str, Any], lang: str = "zh") -> str:
    """Markdown section for partition_roi."""
    from seatunnel_agent.common.utils import fmt_bytes, md_table, normalize_lang

    from .i18n import tp

    lang = normalize_lang(lang)
    lines = [f"### {tp(lang, 'roi_title')}"]
    if not roi["rows"]:
        lines.append(tp(lang, "roi_none"))
    else:
        def saved_cell(r: dict[str, Any]) -> str:
            if r["saved_bytes"] > 0:
                return (f"**{fmt_bytes(r['saved_bytes'])} "
                        f"({r['saved_pct']:g}%)**")
            return fmt_bytes(r["saved_bytes"])

        lines.extend(md_table(
            [tp(lang, "rpt_table_head"), tp(lang, "rpt_col_part"),
             tp(lang, "roi_col_saved"), tp(lang, "roi_col_stmts")],
            [[f"`{r['table']}`", f"`{r['partition_col']}`", saved_cell(r),
              str(r["statements_estimated"])] for r in roi["rows"]]))
    if roi["skipped_tables"]:
        lines.append("")
        lines.append(tp(lang, "roi_skipped") + " " +
                     ", ".join(f"`{t}`" for t in roi["skipped_tables"]))
    return "\n".join(lines)
