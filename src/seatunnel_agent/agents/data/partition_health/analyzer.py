"""Deterministic partition-health check over a partition listing.

Input is the partition listing — CSV with a header or a JSON list::

    [{"table": "ods.click_log", "partition": "dt=2026-10-29",
      "size_gb": 20.5, "rows": 41000000}]

Per table, the rules judge the partitions themselves (freshness already
judges whether they arrive on time): PH001 date gaps inside the
partition sequence (the backfill hole), PH002 empty partitions (zero
size or rows), PH003 size skew (one partition far above the table's
median — a hot-key day or a double-load), PH004 a surging latest
partition and PH005 a shrunken one (yesterday lost volume) — both
against the median of the earlier partitions.  Date-shaped partition
values are required only by the date rules; the others work on any
partition naming.  No database connection.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

__all__ = ["PartitionHealthResult", "PartitionRow", "PhFinding",
           "analyze_partitions", "parse_partition_listing"]

_SKEW_RATIO = (5.0, 20.0)
_SURGE_RATIO = (3.0, 10.0)
_SHRINK_RATIO = 0.3

_PART_DATE = re.compile(r"(\d{4})-?(\d{2})-?(\d{2})")


@dataclass
class PartitionRow:
    table: str
    partition: str
    size_gb: float = 0.0
    rows: int | None = None

    def to_dict(self) -> dict:
        return {"table": self.table, "partition": self.partition,
                "size_gb": self.size_gb, "rows": self.rows}


@dataclass
class PhFinding:
    code: str          # PH001..
    severity: str      # high / mid / low
    table: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "table": self.table, "detail": self.detail}


@dataclass
class PartitionHealthResult:
    tables: int
    partitions: int
    findings: list[PhFinding]

    def to_dict(self) -> dict:
        return {"tables": self.tables, "partitions": self.partitions,
                "findings": [f.to_dict() for f in self.findings]}


def parse_partition_listing(text: str) -> list[PartitionRow]:
    body = (text or "").strip()
    if not body:
        raise ValueError("empty listing / 清单为空")
    if body.startswith("["):
        items = json.loads(body)
    else:
        items = [dict(r) for r in csv.DictReader(io.StringIO(body))]
    rows: list[PartitionRow] = []
    for i, it in enumerate(items, start=1):
        if not isinstance(it, dict) or not (it.get("table") or "").strip():
            raise ValueError(f"row {i}: needs 'table'")
        if not (it.get("partition") or "").strip():
            raise ValueError(f"row {i}: needs 'partition'")
        raw_rows = it.get("rows")
        rows.append(PartitionRow(
            table=str(it["table"]).strip(),
            partition=str(it["partition"]).strip(),
            size_gb=float(it.get("size_gb") or 0),
            rows=int(float(raw_rows)) if raw_rows not in (None, "")
            else None))
    if not rows:
        raise ValueError("no partitions / 没有分区")
    return rows


def _pdate(partition: str) -> date | None:
    m = _PART_DATE.search(partition)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _grade(value: float, thresholds: tuple[float, float]) -> str | None:
    mid, high = thresholds
    if value >= high:
        return "high"
    if value >= mid:
        return "mid"
    return None


def analyze_partitions(rows: list[PartitionRow]) -> PartitionHealthResult:
    by_table: dict[str, list[PartitionRow]] = {}
    for r in rows:
        by_table.setdefault(r.table, []).append(r)
    findings: list[PhFinding] = []

    for table, parts in sorted(by_table.items()):
        # PH001 date gaps inside the dated partition sequence
        dated = sorted((d, p) for p in parts
                       if (d := _pdate(p.partition)) is not None)
        gaps: list[str] = []
        for (a, _), (b, _) in zip(dated, dated[1:]):
            if (b - a).days > 1:
                first = a + timedelta(days=1)
                gaps.append(f"{first.isoformat()} (+{(b - a).days - 1})")
        if gaps:
            findings.append(PhFinding("PH001", "high", table, {
                "gaps": gaps[:5], "gap_count": len(gaps)}))

        # PH002 empty partitions
        empty = [p.partition for p in parts
                 if p.size_gb == 0 or p.rows == 0]
        if empty:
            findings.append(PhFinding("PH002", "mid", table, {
                "count": len(empty), "partitions": sorted(empty)[:5]}))

        # PH003 size skew vs the table median (non-empty partitions)
        sizes = [p.size_gb for p in parts if p.size_gb > 0]
        if len(sizes) >= 4:
            med = _median(sizes)
            worst = max((p for p in parts if p.size_gb > 0),
                        key=lambda p: p.size_gb)
            ratio = worst.size_gb / med if med > 0 else 0.0
            sev = _grade(ratio, _SKEW_RATIO)
            if sev:
                findings.append(PhFinding("PH003", sev, table, {
                    "partition": worst.partition,
                    "size_gb": worst.size_gb, "median_gb": round(med, 2),
                    "ratio": round(ratio, 1)}))

        # PH004 surge / PH005 shrink of the latest dated partition
        if len(dated) >= 4:
            latest = dated[-1][1]
            earlier = [p.size_gb for _, p in dated[:-1] if p.size_gb > 0]
            if earlier and latest.size_gb > 0:
                med = _median(earlier)
                ratio = latest.size_gb / med if med > 0 else 0.0
                sev = _grade(ratio, _SURGE_RATIO)
                if sev:
                    findings.append(PhFinding("PH004", sev, table, {
                        "partition": latest.partition,
                        "size_gb": latest.size_gb,
                        "median_gb": round(med, 2),
                        "ratio": round(ratio, 1)}))
                elif ratio <= _SHRINK_RATIO:
                    findings.append(PhFinding("PH005", "mid", table, {
                        "partition": latest.partition,
                        "size_gb": latest.size_gb,
                        "median_gb": round(med, 2),
                        "ratio": round(ratio, 2)}))

    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code, f.table))
    return PartitionHealthResult(tables=len(by_table),
                                 partitions=len(rows), findings=findings)
