"""Governance advisor — lineage graph × query audit log, advice only.

Deterministic cross-analysis of two assets the project already produces:
the lineage graph (which tables feed which) and the Text2SQL query log
(who queried what, and what got rejected). Outputs *recommendations only* —
it never touches a table (the hard line: 只建议不动手).

Signals:
- **decommission candidates**: tables with no downstream consumers in the
  graph AND no successful query in the audit window
- **hot tables**: most-queried tables (successful runs)
- **rejection-prone tables**: tables whose queries keep getting rejected,
  split out for missing-partition-filter rejections (a governance smell)
- **unqueried leaves**: graph leaves (no downstream) that ARE queried —
  fine, listed to contrast with decommission candidates
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .graph import LineageGraph

_DEFAULT_QLOG = Path("logs") / "text2sql_queries.jsonl"


@dataclass
class GovernanceReport:
    window_days: int
    graph_tables: int = 0
    audited_queries: int = 0
    decommission_candidates: list[str] = field(default_factory=list)
    hot_tables: list[tuple[str, int]] = field(default_factory=list)
    rejection_prone: list[tuple[str, int]] = field(default_factory=list)
    partition_filter_offenders: list[tuple[str, int]] = field(default_factory=list)
    queried_leaves: list[str] = field(default_factory=list)


def load_qlog_records(
    path: str | Path | None = None,
    days: int = 30,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Audit records within the window (bad lines skipped)."""
    p = Path(path) if path else _DEFAULT_QLOG
    if not p.is_file():
        return []
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    records: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = rec.get("timestamp", "")
        try:
            when = datetime.fromisoformat(ts)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if when >= cutoff:
            records.append(rec)
    return records


def analyze_governance(
    graph: LineageGraph,
    records: list[dict[str, Any]],
    days: int = 30,
    top_n: int = 10,
) -> GovernanceReport:
    report = GovernanceReport(window_days=days)
    report.audited_queries = len(records)

    success_counts: Counter[str] = Counter()
    reject_counts: Counter[str] = Counter()
    partition_counts: Counter[str] = Counter()
    for rec in records:
        tables = [str(t).lower() for t in rec.get("matched_tables") or []]
        status = rec.get("status", "")
        if status in ("success", "cache_hit"):
            success_counts.update(tables)
        elif status in ("rejected", "error"):
            reject_counts.update(tables)
            if "partition" in str(rec.get("error", "")).lower():
                partition_counts.update(tables)

    # graph side: leaves = tables nobody consumes (downstream-less, plus
    # isolated nodes that only appear as standalone definitions)
    report.graph_tables = len(graph.nodes)
    leaves = sorted({
        t.lower()
        for t in (*graph.tables_without_downstream(), *graph.isolated_tables())
    })

    # match both qualified ("dwd.orders") and bare ("orders") spellings —
    # qlog table names come from SQL text and may omit the database prefix.
    queried = set(success_counts)
    queried |= {t.rsplit(".", 1)[-1] for t in success_counts}

    def _was_queried(t: str) -> bool:
        return t in queried or t.rsplit(".", 1)[-1] in queried

    report.decommission_candidates = [t for t in leaves if not _was_queried(t)]
    report.queried_leaves = [t for t in leaves if _was_queried(t)]
    report.hot_tables = success_counts.most_common(top_n)
    report.rejection_prone = reject_counts.most_common(top_n)
    report.partition_filter_offenders = partition_counts.most_common(top_n)
    return report


def render_governance_markdown(report: GovernanceReport) -> str:
    lines = ["# 数据治理建议报告", ""]
    lines.append(
        f"> 血缘图 {report.graph_tables} 张表 × 近 {report.window_days} 天 "
        f"{report.audited_queries} 条查询审计。本报告只出建议，不做任何变更。"
    )

    lines.append("")
    lines.append("## 下线候选（无下游消费 + 窗口内无人查询）")
    if report.decommission_candidates:
        for t in report.decommission_candidates:
            lines.append(f"- `{t}` — 建议与 owner 确认后归档/下线")
    else:
        lines.append("- 无")

    lines.append("")
    lines.append("## 热表 Top（成功查询次数）")
    if report.hot_tables:
        lines.append("| 表 | 次数 |")
        lines.append("|---|---|")
        for t, n in report.hot_tables:
            lines.append(f"| `{t}` | {n} |")
    else:
        lines.append("- 窗口内无成功查询记录")

    if report.rejection_prone:
        lines.append("")
        lines.append("## 拒绝/失败高发表")
        lines.append("| 表 | 次数 |")
        lines.append("|---|---|")
        for t, n in report.rejection_prone:
            lines.append(f"| `{t}` | {n} |")

    if report.partition_filter_offenders:
        lines.append("")
        lines.append("## 缺分区过滤被拒（治理异味：口径/习惯问题）")
        lines.append("| 表 | 次数 |")
        lines.append("|---|---|")
        for t, n in report.partition_filter_offenders:
            lines.append(f"| `{t}` | {n} |")

    if report.queried_leaves:
        lines.append("")
        lines.append("## 有人查询的叶子表（正常，仅供对照）")
        lines.append(", ".join(f"`{t}`" for t in report.queried_leaves[:20]))
    return "\n".join(lines)
