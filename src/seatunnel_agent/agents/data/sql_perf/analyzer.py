"""Deterministic EXPLAIN-plan analyzer (Spark / Hive text plans).

The SQL reviewer reads source SQL; this agent reads what the engine
actually decided to do.  Paste the output of ``EXPLAIN [FORMATTED]``
and the parser extracts the plan facts:

* joins — type (SortMerge / BroadcastHash / ShuffledHash / cartesian)
  and count;
* shuffles — ``Exchange`` nodes, including back-to-back re-shuffles;
* scans — per-table ``PartitionFilters`` / ``PushedFilters`` state.

The rules turn those facts into findings (high/medium/low):

  PF001 (high)   cartesian / broadcast-nested-loop join
  PF002 (high)   scan with empty PartitionFilters (full-table read)
  PF003 (medium) Filter sits above a scan whose PushedFilters is empty
  PF004 (medium) consecutive Exchanges on the same stream (re-shuffle)
  PF005 (info)   SortMergeJoin present — evaluate broadcasting the
                 small side
  PF006 (info)   SELECT-star-ish ReadSchema (wide scan, prune columns)
  PF007 (medium) Exchange SinglePartition — the whole stream funnels
                 into one task (global sort / collect), typical of
                 ORDER BY without LIMIT

No engine connection — text in, findings out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SEVERITIES = ("high", "medium", "info")

_JOIN_RE = re.compile(
    r"\b(SortMergeJoin|BroadcastHashJoin|ShuffledHashJoin|"
    r"BroadcastNestedLoopJoin|CartesianProduct|Map Join Operator|"
    r"Merge Join Operator)\b")
_EXCHANGE_RE = re.compile(
    r"\bExchange (hashpartitioning|rangepartitioning|SinglePartition|"
    r"RoundRobinPartitioning)")
_SCAN_RE = re.compile(
    r"\b(?:FileScan|HiveTableScan|Scan)\s+(?:\w+\s+)?"
    r"(?P<table>[\w$]+\.[\w$]+|\w+)\[(?P<cols>[^\]]*)\]")
_PART_FILTERS_RE = re.compile(r"PartitionFilters:\s*\[(?P<val>[^\]]*)\]")
_PUSHED_FILTERS_RE = re.compile(r"PushedFilters:\s*\[(?P<val>[^\]]*)\]")
_FILTER_NODE_RE = re.compile(r"^\s*[*+:(\d)\- ]*Filter\b")


@dataclass
class ScanInfo:
    table: str
    columns: int
    partition_filters: str | None = None  # None: not stated in the plan
    pushed_filters: str | None = None
    filter_above: bool = False  # a Filter node sits above this scan

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "columns": self.columns,
                "partition_filters": self.partition_filters,
                "pushed_filters": self.pushed_filters}


@dataclass
class PerfFinding:
    code: str
    severity: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail}


@dataclass
class PlanReport:
    joins: dict[str, int] = field(default_factory=dict)
    exchanges: int = 0
    single_exchanges: int = 0  # non-broadcast Exchange SinglePartition
    scans: list[ScanInfo] = field(default_factory=list)
    findings: list[PerfFinding] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        from seatunnel_agent.common.severity import severity_counts

        return severity_counts(self.findings, keys=SEVERITIES)

    def to_dict(self) -> dict[str, Any]:
        return {"joins": dict(self.joins), "exchanges": self.exchanges,
                "single_exchanges": self.single_exchanges,
                "scans": [s.to_dict() for s in self.scans],
                "counts": self.counts(),
                "findings": [f.to_dict() for f in self.findings]}


def parse_plan(text: str) -> PlanReport:
    """EXPLAIN text → plan facts (no rules yet)."""
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("empty plan text")
    report = PlanReport()
    for m in _JOIN_RE.finditer(stripped):
        name = m.group(1)
        report.joins[name] = report.joins.get(name, 0) + 1
    report.exchanges = len(_EXCHANGE_RE.findall(stripped))
    report.single_exchanges = sum(
        1 for line in stripped.splitlines()
        if (m := _EXCHANGE_RE.search(line))
        and m.group(1) == "SinglePartition"
        and "BROADCAST" not in line.upper())

    lines = stripped.splitlines()
    filter_above = False
    for line in lines:
        if _FILTER_NODE_RE.match(line):
            filter_above = True
        scan_m = _SCAN_RE.search(line)
        if not scan_m:
            continue
        cols = [c for c in scan_m.group("cols").split(",") if c.strip()]
        scan = ScanInfo(table=scan_m.group("table"), columns=len(cols))
        part_m = _PART_FILTERS_RE.search(line)
        if part_m:
            scan.partition_filters = part_m.group("val").strip()
        pushed_m = _PUSHED_FILTERS_RE.search(line)
        if pushed_m:
            scan.pushed_filters = pushed_m.group("val").strip()
        scan.filter_above = filter_above
        filter_above = False  # consumed by this scan
        report.scans.append(scan)
    if not report.joins and not report.scans and not report.exchanges:
        raise ValueError("no plan operators recognized — paste the "
                         "EXPLAIN output, not the SQL")
    return report


def analyze(text: str) -> PlanReport:
    """Parse the plan and attach the findings."""
    report = parse_plan(text)
    add = report.findings.append
    for bad in ("CartesianProduct", "BroadcastNestedLoopJoin"):
        if report.joins.get(bad):
            add(PerfFinding("PF001", "high",
                            f"{bad} x{report.joins[bad]}"))
    for scan in report.scans:
        if scan.partition_filters == "":
            add(PerfFinding("PF002", "high", scan.table))
        if scan.pushed_filters == "" and scan.filter_above:
            add(PerfFinding("PF003", "medium", scan.table))
        if scan.columns >= 20:
            add(PerfFinding("PF006", "info",
                            f"{scan.table} ({scan.columns} cols)"))
    joins_total = sum(report.joins.values())
    # a join justifies two exchanges (one per side) plus one final
    # aggregation exchange — anything beyond that is a re-shuffle smell
    if report.exchanges > 2 * joins_total + 1:
        add(PerfFinding("PF004", "medium",
                        f"exchanges={report.exchanges}, "
                        f"joins={joins_total}"))
    smj = report.joins.get("SortMergeJoin", 0)
    if smj:
        add(PerfFinding("PF005", "info", f"SortMergeJoin x{smj}"))
    if report.single_exchanges:
        add(PerfFinding("PF007", "medium",
                        f"Exchange SinglePartition x"
                        f"{report.single_exchanges}"))
    rank = {s: i for i, s in enumerate(SEVERITIES)}
    report.findings.sort(key=lambda f: (rank[f.severity], f.code, f.detail))
    return report
