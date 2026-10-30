"""Deterministic sync-strategy advisor.

Input: per-source-table update characteristics (JSON list or CSV) —
row count, daily changed rows, update-timestamp column, primary key,
physical deletes, CDC/binlog availability, latency requirement.
Output per table: the recommended strategy (full / incr_timestamp /
incr_pk / cdc) with the rule trace as reasons and the residual risks.

Rules, in priority order:
1. realtime/minutes latency → CDC when available, otherwise the best
   batch fallback with a latency warning;
2. physical deletes without CDC → full reload (incremental misses them);
3. small or high-churn tables → full reload (simplest, self-healing);
4. update timestamp present → timestamp incremental (upsert with PK,
   append without);
5. PK only, append-only → PK incremental;
6. otherwise → full reload.

No database connection — characteristics come from the inventory.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from typing import Any

STRATEGIES = ("full", "incr_timestamp", "incr_pk", "cdc")
LATENCIES = ("realtime", "minutes", "hours", "daily")

SMALL_ROWS = 1_000_000      # below this, full reload is cheap
HIGH_CHURN = 0.30           # daily change ratio above this → full

_BOOL_FIELDS = ("has_update_ts", "has_pk", "has_deletes", "cdc_available")


@dataclass
class SourceTable:
    table: str
    rows: int = 0
    daily_change_rows: int = 0
    has_update_ts: bool = False
    has_pk: bool = False
    has_deletes: bool = False
    cdc_available: bool = False
    latency: str = "daily"

    @property
    def change_ratio(self) -> float:
        return self.daily_change_rows / self.rows if self.rows else 0.0


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "是")


def _to_table(item: dict[str, Any]) -> SourceTable:
    name = str(item.get("table") or item.get("name") or "").strip()
    if not name:
        raise ValueError(f"table entry missing 'table': {item!r}")
    latency = str(item.get("latency") or "daily").strip().lower()
    if latency not in LATENCIES:
        raise ValueError(f"{name}: latency must be one of {LATENCIES}")
    try:
        rows = int(item.get("rows") or 0)
        changed = int(item.get("daily_change_rows") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: rows/daily_change_rows must be "
                         f"integers") from exc
    if rows < 0 or changed < 0:
        raise ValueError(f"{name}: counts must be >= 0")
    return SourceTable(
        table=name, rows=rows, daily_change_rows=changed, latency=latency,
        **{f: _to_bool(item.get(f, False)) for f in _BOOL_FIELDS})


def parse_tables(text: str) -> list[SourceTable]:
    """JSON (list or ``{"tables": [...]}``) or CSV with headers."""
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("empty inventory")
    if stripped[0] in "[{":
        data = json.loads(stripped)
        if isinstance(data, dict):
            data = data.get("tables")
            if not isinstance(data, list):
                raise ValueError("JSON object needs a 'tables' list")
        if not isinstance(data, list):
            raise ValueError("JSON must be a list of table objects")
        items = data
    else:
        reader = csv.DictReader(io.StringIO(stripped))
        items = [dict(row) for row in reader]
    tables = [_to_table(item) for item in items]
    if not tables:
        raise ValueError("no tables found in inventory")
    return tables


@dataclass
class Recommendation:
    table: str
    strategy: str
    reasons: list[str] = field(default_factory=list)  # i18n reason codes
    risks: list[str] = field(default_factory=list)    # i18n risk codes

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "strategy": self.strategy,
                "reasons": list(self.reasons), "risks": list(self.risks)}


def _recommend_one(t: SourceTable) -> Recommendation:
    rec = Recommendation(table=t.table, strategy="full")
    urgent = t.latency in ("realtime", "minutes")
    if urgent:
        if t.cdc_available:
            rec.strategy = "cdc"
            rec.reasons = ["latency_needs_cdc"]
            if not t.has_pk:
                rec.risks.append("cdc_no_pk")
            return rec
        rec.risks.append("latency_without_cdc")
    if t.has_deletes and not t.cdc_available:
        rec.strategy = "full"
        rec.reasons.append("deletes_without_cdc")
        if t.rows >= SMALL_ROWS:
            rec.risks.append("full_on_big_table")
        return rec
    if t.rows and t.rows < SMALL_ROWS:
        rec.strategy = "full"
        rec.reasons.append("small_table")
        return rec
    if t.rows and t.change_ratio > HIGH_CHURN:
        rec.strategy = "full"
        rec.reasons.append("high_churn")
        return rec
    if t.has_update_ts:
        rec.strategy = "incr_timestamp"
        rec.reasons.append("has_update_ts")
        if t.has_pk:
            rec.reasons.append("pk_upsert")
        else:
            rec.risks.append("incr_no_pk_append_only")
        rec.risks.append("late_update_window")
        return rec
    if t.has_pk:
        rec.strategy = "incr_pk"
        rec.reasons.append("pk_append_only")
        rec.risks.append("pk_incr_misses_updates")
        return rec
    rec.reasons.append("no_incr_column")
    if t.rows >= SMALL_ROWS:
        rec.risks.append("full_on_big_table")
    return rec


@dataclass
class StrategyReport:
    recommendations: list[Recommendation] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = dict.fromkeys(STRATEGIES, 0)
        for rec in self.recommendations:
            out[rec.strategy] += 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {"recommendations": [r.to_dict()
                                    for r in self.recommendations],
                "counts": self.counts()}


def recommend(tables: list[SourceTable]) -> StrategyReport:
    return StrategyReport(
        recommendations=[_recommend_one(t)
                         for t in sorted(tables, key=lambda t: t.table)])
