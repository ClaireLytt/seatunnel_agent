"""Deterministic retention (TTL) advice from a partition inventory.

storage_cost prices what the warehouse holds today; this agent decides
what to keep tomorrow.  Paste a partition inventory — columns ``table``,
``partition`` (``dt=YYYY-MM-DD`` spellings parse), ``size_gb``,
``last_access`` (ISO date, empty = never) — and per table:

* a suggested TTL: the age of the oldest partition anyone still reads,
  plus a 30-day grace, rounded up to 30-day steps;
* archive candidates: partitions past the TTL that nobody has read in
  the active window, with the gigabytes they free;
* purge candidates: the subset never read at all.

"Today" is the newest date seen in the data, so the same inventory
always yields the same advice.  Findings grade the cold share (RP001),
never-read partitions (RP002) and unparseable partition values (RP003).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["RetentionReport", "RetentionFinding", "TableRetention",
           "advise_retention"]

_DATE_RE = re.compile(r"(\d{4})-?(\d{2})-?(\d{2})")
_ACTIVE_DAYS = 90        # a read inside this window keeps a partition warm
_GRACE_DAYS = 30
_COLD_MED = 0.25
_COLD_HIGH = 0.50


def _partition_date(value: str) -> date | None:
    m = _DATE_RE.search(value or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


@dataclass
class TableRetention:
    table: str
    partitions: int = 0
    total_gb: float = 0.0
    cold_gb: float = 0.0
    ttl_days: int | None = None
    archive: list[str] = field(default_factory=list)
    purge: list[str] = field(default_factory=list)

    @property
    def cold_share(self) -> float:
        return self.cold_gb / self.total_gb if self.total_gb else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "partitions": self.partitions,
                "total_gb": round(self.total_gb, 2),
                "cold_gb": round(self.cold_gb, 2),
                "cold_share": round(self.cold_share, 4),
                "ttl_days": self.ttl_days,
                "archive": list(self.archive),
                "purge": list(self.purge)}


@dataclass
class RetentionFinding:
    code: str            # RP001..RP003
    severity: str        # high | medium | low
    table: str
    value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "table": self.table, "value": round(self.value, 4)}


@dataclass
class RetentionReport:
    today: str
    tables: list[TableRetention] = field(default_factory=list)
    findings: list[RetentionFinding] = field(default_factory=list)
    total_gb: float = 0.0
    reclaimable_gb: float = 0.0
    skipped: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"today": self.today,
                "total_gb": round(self.total_gb, 2),
                "reclaimable_gb": round(self.reclaimable_gb, 2),
                "counts": self.counts(),
                "tables": [t.to_dict() for t in self.tables],
                "findings": [f.to_dict() for f in self.findings],
                "skipped": list(self.skipped)}


def advise_retention(headers: list[str], rows: list[dict[str, str | None]],
                     active_days: int = _ACTIVE_DAYS) -> RetentionReport:
    """Partition inventory → per-table TTL advice, worst cold share first."""
    needed = {"table", "partition", "size_gb", "last_access"}
    missing = needed - {h.lower() for h in headers}
    if missing:
        raise ValueError("inventory needs columns table/partition/"
                         f"size_gb/last_access — missing: "
                         f"{', '.join(sorted(missing))}")
    if not rows:
        raise ValueError("the inventory has no rows")
    if active_days < 1:
        raise ValueError("active_days must be positive")
    col = {h.lower(): h for h in headers}

    parsed = []       # (table, partition, pdate, size, adate)
    skipped: list[str] = []
    all_dates: list[date] = []
    for i, r in enumerate(rows):
        table = str(r.get(col["table"]) or "").strip()
        part = str(r.get(col["partition"]) or "").strip()
        if not table or not part:
            raise ValueError(f"row {i + 1}: table and partition are "
                             "required")
        try:
            size = float(r.get(col["size_gb"]) or 0)
        except ValueError:
            raise ValueError(f"row {i + 1}: size_gb must be a number")
        pdate = _partition_date(part)
        if pdate is None:
            skipped.append(f"{table}/{part}")
            continue
        raw_access = str(r.get(col["last_access"]) or "").strip()
        adate = _partition_date(raw_access) if raw_access else None
        parsed.append((table, part, pdate, size, adate))
        all_dates.append(pdate)
        if adate:
            all_dates.append(adate)
    if not parsed:
        raise ValueError("no partition carries a parseable date "
                         "(dt=YYYY-MM-DD spellings)")

    today = max(all_dates)
    report = RetentionReport(today=today.isoformat(), skipped=skipped)

    by_table: dict[str, list] = {}
    for item in parsed:
        by_table.setdefault(item[0], []).append(item)

    for table in sorted(by_table):
        items = by_table[table]
        t = TableRetention(table=table, partitions=len(items))
        warm_ages = []
        for _, _part, pdate, size, adate in items:
            t.total_gb += size
            age = (today - pdate).days
            warm = adate is not None and (today - adate).days <= active_days
            if warm:
                warm_ages.append(age)
        if warm_ages:
            ttl = max(warm_ages) + _GRACE_DAYS
            t.ttl_days = max(30, math.ceil(ttl / 30) * 30)
        else:
            t.ttl_days = 30     # nobody reads it — keep the minimum
        for _, part, pdate, size, adate in sorted(
                items, key=lambda it: it[2]):
            age = (today - pdate).days
            warm = adate is not None and (today - adate).days <= active_days
            if age > t.ttl_days and not warm:
                t.cold_gb += size
                t.archive.append(part)
                if adate is None:
                    t.purge.append(part)
        report.tables.append(t)
        report.total_gb += t.total_gb
        report.reclaimable_gb += t.cold_gb

        if t.cold_share >= _COLD_MED:
            report.findings.append(RetentionFinding(
                code="RP001",
                severity="high" if t.cold_share >= _COLD_HIGH
                else "medium",
                table=table, value=t.cold_share))
        if t.purge:
            report.findings.append(RetentionFinding(
                code="RP002", severity="medium", table=table,
                value=len(t.purge)))
    if skipped:
        report.findings.append(RetentionFinding(
            code="RP003", severity="low", table="-", value=len(skipped)))

    report.tables.sort(key=lambda t: -t.cold_share)
    order = {"high": 0, "medium": 1, "low": 2}
    report.findings.sort(key=lambda f: (order[f.severity], f.code, f.table))
    return report
