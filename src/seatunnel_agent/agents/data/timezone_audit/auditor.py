"""Deterministic timestamp-semantics audit over data rows.

A timestamp column can be wrong four ways that no type checker sees:
UTC and local time mixed in one column, seconds mixed with
milliseconds, epoch-zero/overflow sentinels, and ISO strings whose
explicit offsets disagree.  Paste the rows (sample_profile's parser
reused) and every timestamp-shaped column is audited:

* TZ001 high — ISO values with *different explicit offsets* (``Z`` /
  ``+08:00`` / none) in one column: direct evidence of mixed zones;
* TZ002 high — epoch values mixing units (10-digit seconds beside
  13-digit milliseconds): aggregates off by a factor of 1000;
* TZ003 medium — a bimodal hour-of-day histogram with the two modes
  ~8h apart and both carrying real mass: the classic UTC-vs-CN smell
  (an honest heuristic, not proof);
* TZ004 medium — sentinel years (before 1980: the epoch-zero family;
  after 2100: overflow garbage), counted.

Columns qualify when their name looks time-ish or 80% of their values
parse as timestamps.  No database connection.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["TimezoneAudit", "TzFinding", "audit_timezones"]

_TIME_NAME = re.compile(r"(^|_)(ts|time|at|date|created|updated)(_|$)",
                        re.IGNORECASE)
_EPOCH_RE = re.compile(r"^\d{10}(\d{3}(\d{3})?)?$")
_PARSE_SHARE = 0.8
_BIMODAL_GAP = (7, 9)
_BIMODAL_MASS = 0.2
_YEAR_LO, _YEAR_HI = 1980, 2100


@dataclass
class ColumnAudit:
    name: str
    values: int = 0
    kinds: dict[str, int] = field(default_factory=dict)   # iso|s|ms|us
    offsets: dict[str, int] = field(default_factory=dict)  # Z|+08:00|naive
    sentinel: int = 0
    hour_modes: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "values": self.values,
                "kinds": dict(self.kinds), "offsets": dict(self.offsets),
                "sentinel": self.sentinel,
                "hour_modes": list(self.hour_modes)}


@dataclass
class TzFinding:
    code: str            # TZ001..TZ004
    severity: str        # high | medium
    column: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "column": self.column, "detail": self.detail}


@dataclass
class TimezoneAudit:
    columns: list[ColumnAudit] = field(default_factory=list)
    findings: list[TzFinding] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"columns_audited": len(self.columns),
                "counts": self.counts(),
                "columns": [c.to_dict() for c in self.columns],
                "findings": [f.to_dict() for f in self.findings]}


def _parse_value(v: str) -> tuple[str, datetime] | None:
    v = v.strip()
    if _EPOCH_RE.match(v):
        n = int(v)
        if len(v) == 10:
            kind, seconds = "s", n
        elif len(v) == 13:
            kind, seconds = "ms", n / 1000
        else:
            kind, seconds = "us", n / 1_000_000
        try:
            return kind, datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return kind, datetime(2101, 1, 1, tzinfo=timezone.utc)
    try:
        return "iso", datetime.fromisoformat(v)
    except ValueError:
        return None


def _offset_label(dt: datetime) -> str:
    if dt.tzinfo is None:
        return "naive"
    off = dt.utcoffset()
    total = int(off.total_seconds() // 60) if off else 0
    if total == 0:
        return "Z"
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 60:02d}:{total % 60:02d}"


def _bimodal_hours(hours: list[int]) -> list[int]:
    if len(hours) < 10:
        return []
    hist = Counter(hours)
    (h1, c1), *rest = hist.most_common()
    for h2, c2 in rest:
        gap = min(abs(h1 - h2), 24 - abs(h1 - h2))
        if (_BIMODAL_GAP[0] <= gap <= _BIMODAL_GAP[1]
                and c1 / len(hours) >= _BIMODAL_MASS
                and c2 / len(hours) >= _BIMODAL_MASS):
            return sorted([h1, h2])
    return []


def audit_timezones(headers: list[str],
                    rows: list[dict[str, str | None]]) -> TimezoneAudit:
    """Rows → per-column timestamp-semantics findings."""
    if not headers or not rows:
        raise ValueError("the sample needs a header and at least one row")

    audit = TimezoneAudit()
    for h in headers:
        raw = [str(r[h]) for r in rows if r.get(h) not in (None, "")]
        if not raw:
            continue
        parsed = [(v, _parse_value(v)) for v in raw]
        hits = [(v, p) for v, p in parsed if p is not None]
        timeish_name = bool(_TIME_NAME.search(h))
        if not hits or (not timeish_name
                        and len(hits) / len(raw) < _PARSE_SHARE):
            continue

        col = ColumnAudit(name=h, values=len(hits))
        hours: list[int] = []
        for _, (kind, dt) in hits:
            col.kinds[kind] = col.kinds.get(kind, 0) + 1
            if kind == "iso":
                label = _offset_label(dt)
                col.offsets[label] = col.offsets.get(label, 0) + 1
            if dt.year < _YEAR_LO or dt.year > _YEAR_HI:
                col.sentinel += 1
            else:
                hours.append(dt.hour)
        col.hour_modes = _bimodal_hours(hours)
        audit.columns.append(col)

        if len(col.offsets) > 1:
            audit.findings.append(TzFinding(
                "TZ001", "high", h,
                ", ".join(f"{k}x{v}" for k, v in
                          sorted(col.offsets.items()))))
        epoch_kinds = {k for k in col.kinds if k != "iso"}
        if len(epoch_kinds) > 1:
            audit.findings.append(TzFinding(
                "TZ002", "high", h,
                ", ".join(f"{k}x{col.kinds[k]}" for k in
                          sorted(epoch_kinds))))
        if col.hour_modes:
            audit.findings.append(TzFinding(
                "TZ003", "medium", h,
                f"{col.hour_modes[0]:02d}h / {col.hour_modes[1]:02d}h"))
        if col.sentinel:
            audit.findings.append(TzFinding(
                "TZ004", "medium", h, str(col.sentinel)))

    if not audit.columns:
        raise ValueError("no timestamp-shaped column found (time-ish "
                         "name, or 80% parseable values)")
    order = {"high": 0, "medium": 1}
    audit.findings.sort(key=lambda f: (order[f.severity], f.code,
                                       f.column))
    return audit
