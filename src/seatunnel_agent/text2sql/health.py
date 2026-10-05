"""Table health score + governance advisor (资产健康分 / 僵尸表 / 生命周期).

Deterministic scoring over signals the platform already collects — no new
probes, no LLM:

- heat (40):   query usage from the qlog audit trail (log-scaled)
- docs (40):   table comment + share of commented columns
- lineage (20): the table participates in the lineage graph (has any
  upstream or downstream edge); omitted from the denominator when no
  graph is supplied, so scores stay comparable within one run

Governance findings ride on the same signals:

- zombie_table : never queried AND no lineage downstream (graph required)
- stale_partitioned : partitioned table not queried in ``stale_days``
  (or never) — lifecycle/TTL review candidate
- pii_exposure : columns matching the PII ruleset (name/comment), as a
  flag for masking review — informational, not a score penalty
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from ..pii_scan.rules import DEFAULT_RULES
from ..pii_scan.scanner import ColumnRef, _match_rules
from .schema import SchemaStore, TableSchema

#: component weights with a lineage graph / without one
_WEIGHTS_FULL = {"heat": 40, "docs": 40, "lineage": 20}
_WEIGHTS_NO_GRAPH = {"heat": 50, "docs": 50}

#: usage count that saturates the heat component
_HEAT_SATURATION = 50


def _usage_from_qlog(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """{table(lower): {count, last_used(iso str)}} from qlog records."""
    usage: dict[str, dict[str, Any]] = {}
    for rec in records:
        ts = str(rec.get("timestamp", ""))
        for t in rec.get("matched_tables") or []:
            key = str(t).lower()
            slot = usage.setdefault(key, {"count": 0, "last_used": ""})
            slot["count"] += 1
            if ts > slot["last_used"]:
                slot["last_used"] = ts
    return usage


def _docs_ratio(table: TableSchema) -> float:
    """0..1: table comment counts 0.4, commented-column share counts 0.6."""
    cols = table.columns + table.partition_columns
    commented = sum(1 for c in cols if (c.comment or "").strip())
    col_share = commented / len(cols) if cols else 0.0
    return 0.4 * (1.0 if (table.comment or "").strip() else 0.0) + 0.6 * col_share


def _heat_ratio(count: int) -> float:
    """0..1 on a log scale; saturates at _HEAT_SATURATION queries."""
    if count <= 0:
        return 0.0
    return min(1.0, math.log1p(count) / math.log1p(_HEAT_SATURATION))


def _pii_columns(table: TableSchema) -> list[str]:
    hits: list[str] = []
    for c in table.columns + table.partition_columns:
        ref = ColumnRef(table=table.full_name, column=c.name,
                        col_type=c.dtype, comment=c.comment or "")
        if _match_rules(ref, DEFAULT_RULES) is not None:
            hits.append(c.name)
    return hits


def score_tables(
    store: SchemaStore,
    qlog_records: list[dict[str, Any]] | None = None,
    lineage_graph: Any = None,
    now: datetime | None = None,
    stale_days: int = 90,
) -> dict[str, Any]:
    """Score every whitelisted table and derive governance findings.

    ``lineage_graph`` is a ``data_lineage.graph.LineageGraph`` (optional);
    without it the lineage component and zombie detection are skipped.
    """
    now = now or datetime.now(timezone.utc)
    usage = _usage_from_qlog(qlog_records or [])
    weights = _WEIGHTS_FULL if lineage_graph is not None else _WEIGHTS_NO_GRAPH
    stale_cutoff = (now - timedelta(days=stale_days)).isoformat()

    rows: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for table in store.tables:
        name = table.full_name
        u = usage.get(name.lower(), {"count": 0, "last_used": ""})
        components: dict[str, float] = {
            "heat": round(weights["heat"] * _heat_ratio(u["count"]), 2),
            "docs": round(weights["docs"] * _docs_ratio(table), 2),
        }

        downstream = upstream = 0
        if lineage_graph is not None:
            upstream = lineage_graph.upstream_of(name, depth=1).upstream_count
            downstream = lineage_graph.downstream_of(
                name, depth=1).downstream_count
            components["lineage"] = float(
                weights["lineage"] if (upstream or downstream) else 0)

        pii_cols = _pii_columns(table)
        flags: list[str] = []
        if pii_cols:
            flags.append("pii")
            findings.append({
                "kind": "pii_exposure", "table": name,
                "columns": pii_cols,
                "advice": "确认呈现层已脱敏（T2S_MASKING）或下游已 mask",
            })
        if lineage_graph is not None and u["count"] == 0 and downstream == 0:
            flags.append("zombie")
            findings.append({
                "kind": "zombie_table", "table": name,
                "advice": "审计期内无查询且血缘无下游，确认后可下线/归档",
            })
        if table.partition_columns and (
                not u["last_used"] or u["last_used"] < stale_cutoff):
            flags.append("stale")
            findings.append({
                "kind": "stale_partitioned", "table": name,
                "last_used": u["last_used"] or None,
                "advice": f"分区表超过 {stale_days} 天未被查询，"
                          "建议设置生命周期/TTL 或归档历史分区",
            })

        rows.append({
            "table": name,
            "score": round(sum(components.values()), 2),
            "components": components,
            "query_count": u["count"],
            "last_used": u["last_used"] or None,
            "flags": flags,
        })

    rows.sort(key=lambda r: (r["score"], r["table"]))
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "weights": dict(weights),
        "table_count": len(rows),
        "tables": rows,
        "findings": findings,
    }


def render_health_markdown(report: dict[str, Any], top: int = 20) -> str:
    """Worst-first health ranking + governance findings, as Markdown."""
    lines = [
        "# 数据资产健康报告",
        "",
        f"- 表数: {report['table_count']}  "
        f"- 权重: {report['weights']}  "
        f"- 生成时间: {report['generated_at']}",
        "",
        "## 健康分排行（低分在前）",
        "",
        "| 表 | 分 | 查询次数 | 最近使用 | 标记 |",
        "|---|---|---|---|---|",
    ]
    for r in report["tables"][:top]:
        lines.append(
            f"| {r['table']} | {r['score']} | {r['query_count']} "
            f"| {r['last_used'] or '-'} | {', '.join(r['flags']) or '-'} |"
        )
    findings = report.get("findings") or []
    if findings:
        lines += ["", "## 治理建议", ""]
        for f in findings:
            extra = f" ({', '.join(f['columns'])})" if f.get("columns") else ""
            lines.append(f"- **{f['kind']}** {f['table']}{extra}: {f['advice']}")
    lines.append("")
    return "\n".join(lines)
