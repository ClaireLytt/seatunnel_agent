"""Deterministic small-file compaction planning from a file inventory.

A thousand 2 MB files serve a query worse than eight 256 MB ones, and
the NameNode pays for every one of them.  Paste the file inventory —
columns ``table``, ``partition``, ``file_count``, ``total_mb`` — and
the plan finds where compaction pays:

* a partition is **small-file** when its average file size sits under
  ``small_mb`` (default 32 MB) and it holds more than ``min_files``
  files (default 10) — tiny-but-few partitions are left alone;
* merge candidates are ranked by the files they free
  (``file_count - ceil(total_mb / target_mb)``, target 256 MB), each
  with a ready ``CONCATENATE`` / ``INSERT OVERWRITE`` template;
* CP001 — a table whose small-file partitions hold over 25% of its
  files (high from 50%); CP002 high — any partition holding 1000+
  files: a NameNode pressure point on its own.

partition_health examines partition *sizes*; this examines the *file
counts inside them*.  No cluster connection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["CompactPlan", "CompactFinding", "plan_compaction"]

_SMALL_MB = 32.0
_MIN_FILES = 10
_TARGET_MB = 256.0
_SHARE_MED, _SHARE_HIGH = 0.25, 0.50
_EXTREME_FILES = 1000
_TOP = 10


@dataclass
class MergeCandidate:
    table: str
    partition: str
    file_count: int
    total_mb: float
    avg_mb: float
    files_after: int

    @property
    def files_freed(self) -> int:
        return max(0, self.file_count - self.files_after)

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "partition": self.partition,
                "file_count": self.file_count,
                "total_mb": round(self.total_mb, 1),
                "avg_mb": round(self.avg_mb, 2),
                "files_after": self.files_after,
                "files_freed": self.files_freed}


@dataclass
class CompactFinding:
    code: str            # CP001 | CP002
    severity: str        # high | medium
    table: str
    detail: str = ""
    value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "table": self.table, "detail": self.detail,
                "value": round(self.value, 4)}


@dataclass
class CompactPlan:
    partitions: int = 0
    files_total: int = 0
    files_freed: int = 0
    candidates: list[MergeCandidate] = field(default_factory=list)
    findings: list[CompactFinding] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"partitions": self.partitions,
                "files_total": self.files_total,
                "files_freed": self.files_freed,
                "counts": self.counts(),
                "candidates": [c.to_dict() for c in self.candidates],
                "findings": [f.to_dict() for f in self.findings]}


def plan_compaction(headers: list[str],
                    rows: list[dict[str, str | None]],
                    small_mb: float = _SMALL_MB,
                    target_mb: float = _TARGET_MB) -> CompactPlan:
    """File inventory → ranked merge candidates, graded pressure."""
    needed = {"table", "partition", "file_count", "total_mb"}
    missing = needed - {h.lower() for h in headers}
    if missing:
        raise ValueError("inventory needs columns table/partition/"
                         f"file_count/total_mb — missing: "
                         f"{', '.join(sorted(missing))}")
    if not rows:
        raise ValueError("the inventory has no rows")
    if small_mb <= 0 or target_mb <= small_mb:
        raise ValueError("need 0 < small_mb < target_mb")
    col = {h.lower(): h for h in headers}

    plan = CompactPlan()
    table_files: dict[str, int] = {}
    table_small: dict[str, int] = {}
    for i, r in enumerate(rows):
        table = str(r.get(col["table"]) or "").strip()
        part = str(r.get(col["partition"]) or "").strip()
        if not table or not part:
            raise ValueError(f"row {i + 1}: table and partition are "
                             "required")
        try:
            files = int(float(r.get(col["file_count"]) or 0))
            mb = float(r.get(col["total_mb"]) or 0)
        except ValueError:
            raise ValueError(f"row {i + 1}: file_count and total_mb must "
                             "be numbers")
        if files < 0 or mb < 0:
            raise ValueError(f"row {i + 1}: counts must not be negative")
        plan.partitions += 1
        plan.files_total += files
        table_files[table] = table_files.get(table, 0) + files

        avg = mb / files if files else 0.0
        small = files > _MIN_FILES and avg < small_mb
        if small:
            table_small[table] = table_small.get(table, 0) + files
            after = max(1, math.ceil(mb / target_mb))
            plan.candidates.append(MergeCandidate(
                table=table, partition=part, file_count=files,
                total_mb=mb, avg_mb=avg, files_after=after))
        if files >= _EXTREME_FILES:
            plan.findings.append(CompactFinding(
                "CP002", "high", table, detail=part, value=files))

    plan.candidates.sort(key=lambda c: -c.files_freed)
    plan.files_freed = sum(c.files_freed for c in plan.candidates)

    for table, total in sorted(table_files.items()):
        small = table_small.get(table, 0)
        if not total or not small:
            continue
        share = small / total
        if share >= _SHARE_MED:
            plan.findings.append(CompactFinding(
                "CP001",
                "high" if share >= _SHARE_HIGH else "medium",
                table, value=share))

    order = {"high": 0, "medium": 1}
    plan.findings.sort(key=lambda f: (order[f.severity], f.code, f.table))
    return plan
