# -*- coding: utf-8 -*-
"""Cost analysis over the query audit log.

Deterministic only — no LLM, no database, nothing executed. All numbers
come from the JSONL audit records that the Text2SQL executor already
writes (``exec_time_ms``, ``row_count``, ``matched_tables``, ``status``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..data_lineage.governance import load_qlog_records
from ..text2sql.partition import has_partition_filter

_NUM = re.compile(r"\b\d+(?:\.\d+)?\b")
_STR = re.compile(r"'[^']*'")
_WS = re.compile(r"\s+")

# Default partition column candidates checked when no schema is supplied.
DEFAULT_PARTITION_COLS = ("dt", "pt", "ds")


def normalize_template(sql: str) -> str:
    """Mask literals so the same query shape aggregates into one template."""
    sql = _STR.sub("'?'", sql)
    sql = _NUM.sub("?", sql)
    return _WS.sub(" ", sql).strip().lower()


@dataclass
class QueryCost:
    template: str
    sample_sql: str
    runs: int = 0
    total_ms: int = 0
    max_ms: int = 0
    total_rows: int = 0
    tables: list[str] = field(default_factory=list)
    missing_partition_filter: bool = False
    skew_categories: list[str] = field(default_factory=list)

    @property
    def avg_ms(self) -> int:
        return self.total_ms // self.runs if self.runs else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "template": self.template, "sample_sql": self.sample_sql,
            "runs": self.runs, "total_ms": self.total_ms,
            "avg_ms": self.avg_ms, "max_ms": self.max_ms,
            "total_rows": self.total_rows, "tables": self.tables,
            "missing_partition_filter": self.missing_partition_filter,
            "skew_categories": self.skew_categories,
        }


@dataclass
class TableCost:
    table: str
    queries: int = 0
    total_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "queries": self.queries,
                "total_ms": self.total_ms}


@dataclass
class CostReport:
    days: int = 30
    record_count: int = 0
    success_count: int = 0
    total_ms: int = 0
    top_queries: list[QueryCost] = field(default_factory=list)
    table_costs: list[TableCost] = field(default_factory=list)
    no_partition_filter: list[QueryCost] = field(default_factory=list)
    qlog_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "days": self.days, "record_count": self.record_count,
            "success_count": self.success_count, "total_ms": self.total_ms,
            "top_queries": [q.to_dict() for q in self.top_queries],
            "table_costs": [t.to_dict() for t in self.table_costs],
            "no_partition_filter":
                [q.to_dict() for q in self.no_partition_filter],
            "qlog_path": self.qlog_path,
        }


def _missing_partition_filter(sql: str,
                              partition_cols: tuple[str, ...]) -> bool:
    if not sql or not re.search(r"\bfrom\b", sql, re.IGNORECASE):
        return False
    return not any(has_partition_filter(sql, col) for col in partition_cols)


def analyze_cost(
    qlog_path: str | Path | None = None,
    days: int = 30,
    top_n: int = 10,
    partition_cols: tuple[str, ...] = DEFAULT_PARTITION_COLS,
    scan_patterns: bool = True,
    dialect: str = "hive",
) -> CostReport:
    """Aggregate audit records into a cost report.

    ``scan_patterns`` runs the data_skew static rules on each Top-N sample
    SQL to surface expensive patterns (global distinct, cartesian join,
    global ORDER BY, ...).
    """
    records = load_qlog_records(qlog_path, days=days)
    report = CostReport(days=days, record_count=len(records),
                        qlog_path=str(qlog_path or ""))

    buckets: dict[str, QueryCost] = {}
    table_ms: dict[str, TableCost] = {}
    for rec in records:
        sql = (rec.get("generated_sql") or "").strip()
        status = (rec.get("status") or "").lower()
        if not sql or status not in ("success", "cache_hit"):
            continue
        report.success_count += 1
        ms = int(rec.get("exec_time_ms") or 0)
        rows = int(rec.get("row_count") or 0)
        report.total_ms += ms

        template = normalize_template(sql)
        bucket = buckets.get(template)
        if bucket is None:
            bucket = QueryCost(
                template=template, sample_sql=sql,
                tables=sorted({str(t).lower()
                               for t in rec.get("matched_tables") or []}),
                missing_partition_filter=_missing_partition_filter(
                    sql, partition_cols))
            buckets[template] = bucket
        bucket.runs += 1
        bucket.total_ms += ms
        bucket.max_ms = max(bucket.max_ms, ms)
        bucket.total_rows += rows

        for tbl in rec.get("matched_tables") or []:
            tbl = str(tbl).lower()
            tc = table_ms.setdefault(tbl, TableCost(table=tbl))
            tc.queries += 1
            tc.total_ms += ms

    ranked = sorted(buckets.values(),
                    key=lambda q: q.total_ms, reverse=True)
    report.top_queries = ranked[:top_n]
    report.no_partition_filter = [
        q for q in ranked if q.missing_partition_filter][:top_n]
    report.table_costs = sorted(
        table_ms.values(), key=lambda t: t.total_ms, reverse=True)[:top_n]

    if scan_patterns:
        _scan_expensive_patterns(report.top_queries, dialect)
    return report


def _scan_expensive_patterns(queries: list[QueryCost], dialect: str) -> None:
    """Tag each top query with data_skew rule categories (best effort)."""
    try:
        from ..data_skew.detector import detect_skew
    except Exception:                                   # pragma: no cover
        return
    for q in queries:
        try:
            findings, _hints = detect_skew(q.sample_sql, dialect=dialect)
        except Exception:
            continue
        q.skew_categories = sorted({f.category for f in findings})
