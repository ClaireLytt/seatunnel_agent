"""Deterministic storage-cost governance over an inventory listing.

The table inventory is parsed by the asset_value parser (reused), with
two extensions: an optional ``avg_file_mb`` column per table and an
optional partition listing (CSV/JSON rows of table, partition, size_gb).
Three rules turn the numbers into actions — cold-tier candidates (big
tables nobody touched for months), expired partitions (date-shaped
partition values older than the retention window), and small-file
compaction (tiny average file sizes) — each with the estimated GB it
frees or moves.  No database connection.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from seatunnel_agent.agents.data.asset_value import AssetRow, parse_inventory

__all__ = ["CostAction", "CostResult", "analyze_storage",
           "parse_partitions", "run_storage_analysis"]

_COLD_DAYS = 90          # untouched this long -> cold-tier candidate
_COLD_MIN_GB = 100.0     # only big tables are worth moving
_SMALL_FILE_MB = 16.0    # avg file under this -> compaction

_PART_DATE = re.compile(r"(\d{4})-?(\d{2})-?(\d{2})")


@dataclass
class CostAction:
    kind: str              # cold_tier / drop_partitions / compact
    table: str
    freed_gb: float
    severity: str          # high / mid / low
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "table": self.table,
                "freed_gb": round(self.freed_gb, 1),
                "severity": self.severity, "detail": self.detail}


@dataclass
class CostResult:
    today: str
    total_gb: float
    reclaimable_gb: float
    actions: list[CostAction]

    def to_dict(self) -> dict:
        return {"today": self.today, "total_gb": round(self.total_gb, 1),
                "reclaimable_gb": round(self.reclaimable_gb, 1),
                "actions": [a.to_dict() for a in self.actions]}


def parse_partitions(text: str) -> list[dict]:
    """Partition listing: CSV (table,partition,size_gb) or JSON rows."""
    body = (text or "").strip()
    if not body:
        return []
    if body.startswith("["):
        items = json.loads(body)
    else:
        items = [dict(r) for r in csv.DictReader(io.StringIO(body))]
    rows = []
    for i, it in enumerate(items, start=1):
        if not isinstance(it, dict) or not (it.get("table") or "").strip():
            raise ValueError(f"partition row {i}: needs 'table'")
        rows.append({"table": str(it["table"]).strip(),
                     "partition": str(it.get("partition") or "").strip(),
                     "size_gb": float(it.get("size_gb") or 0)})
    return rows


def _partition_date(partition: str) -> date | None:
    m = _PART_DATE.search(partition)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _days_since(day: str, today: date) -> int | None:
    try:
        return (today - date.fromisoformat(day)).days
    except ValueError:
        return None


def analyze_storage(rows: list[AssetRow], partitions: list[dict],
                    retention_days: int = 365,
                    today: date | None = None) -> CostResult:
    today = today or date.today()
    actions: list[CostAction] = []

    # SC: cold-tier candidates
    for r in rows:
        days = _days_since(r.last_access, today)
        if (r.size_gb >= _COLD_MIN_GB and r.access_cnt_30d == 0
                and (days is None or days > _COLD_DAYS)):
            actions.append(CostAction(
                "cold_tier", r.table, r.size_gb,
                "high" if r.size_gb >= 1000 else "mid",
                {"days_since_access": days,
                 "downstream_cnt": r.downstream_cnt}))

    # SC: expired partitions
    cutoff = today - timedelta(days=retention_days)
    expired: dict[str, dict] = {}
    for p in partitions:
        d = _partition_date(p["partition"])
        if d is not None and d < cutoff:
            bucket = expired.setdefault(p["table"], {
                "count": 0, "gb": 0.0, "oldest": p["partition"]})
            bucket["count"] += 1
            bucket["gb"] += p["size_gb"]
            if (_partition_date(bucket["oldest"]) or d) >= d:
                bucket["oldest"] = p["partition"]
    for table, b in expired.items():
        actions.append(CostAction(
            "drop_partitions", table, b["gb"],
            "high" if b["gb"] >= 500 else "mid",
            {"expired_partitions": b["count"], "oldest": b["oldest"],
             "retention_days": retention_days}))

    # SC: small-file compaction (needs the optional avg_file_mb column)
    for r in rows:
        raw = r.extra.get("avg_file_mb")
        if raw in (None, ""):
            continue
        avg = float(raw)
        if 0 < avg < _SMALL_FILE_MB:
            actions.append(CostAction(
                "compact", r.table, 0.0, "low",
                {"avg_file_mb": avg, "threshold_mb": _SMALL_FILE_MB}))

    order = {"high": 0, "mid": 1, "low": 2}
    actions.sort(key=lambda a: (order[a.severity], -a.freed_gb, a.table))
    reclaimable = sum(a.freed_gb for a in actions)
    return CostResult(today=today.isoformat(),
                      total_gb=sum(r.size_gb for r in rows),
                      reclaimable_gb=reclaimable, actions=actions)


def run_storage_analysis(inventory_text: str, partitions_text: str = "",
                         retention_days: int = 365,
                         today: date | None = None) -> CostResult:
    return analyze_storage(parse_inventory(inventory_text),
                           parse_partitions(partitions_text),
                           retention_days=retention_days, today=today)
