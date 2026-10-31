"""Deterministic SQL resource-cost estimator.

Input: one SQL statement plus a per-table stats inventory (rows, bytes,
partition count, partition column).  The estimate is built bottom-up
and every modelling assumption is printed with the result — this is an
order-of-magnitude card, not a promise:

* scan per table — full bytes, discounted by partition pruning
  (equality on the declared partition column → 1/partitions) and by
  column pruning (selected/total when the inventory lists columns);
* shuffle — join sides are exchanged unless one side fits the
  broadcast threshold; GROUP BY / DISTINCT exchanges its input once;
* output rows — joins keep the larger side (FK assumption),
  aggregation shrinks by the stated factor;
* cores/time — bytes over the stated per-core throughput, with a
  0.5x–2x uncertainty band and a suggested parallelism.

Tables missing from the inventory are reported and excluded from the
totals rather than silently guessed.  No database connection.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from typing import Any

# modelling assumptions — surfaced verbatim in the report
BROADCAST_BYTES = 10 * 1024 * 1024        # small side broadcast threshold
AGG_SHRINK = 10                           # GROUP BY output shrink factor
CORE_THROUGHPUT = 100 * 1024 * 1024       # bytes/second per core
MEMORY_HEADROOM = 3                       # peak partition x safety factor
SHUFFLE_PARTITIONS = 200
UNCERTAINTY = (0.5, 2.0)

_IDENT = r"[\w.]+"


@dataclass
class TableStats:
    table: str
    rows: int = 0
    bytes: int = 0
    partitions: int = 1
    partition_col: str = ""
    columns: int = 0  # 0: unknown


def parse_stats(text: str) -> dict[str, TableStats]:
    """JSON (list / {"tables": [...]}) or CSV with headers → stats map."""
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("empty stats inventory")
    if stripped[0] in "[{":
        data = json.loads(stripped)
        if isinstance(data, dict):
            data = data.get("tables")
        if not isinstance(data, list):
            raise ValueError("stats JSON must be a list or {'tables': []}")
        items = data
    else:
        items = [dict(r) for r in csv.DictReader(io.StringIO(stripped))]
    out: dict[str, TableStats] = {}
    for item in items:
        name = str(item.get("table") or "").strip().lower()
        if not name:
            raise ValueError(f"stats entry missing 'table': {item!r}")
        try:
            out[name] = TableStats(
                table=name,
                rows=int(item.get("rows") or 0),
                bytes=int(item.get("bytes") or 0),
                partitions=max(int(item.get("partitions") or 1), 1),
                partition_col=str(item.get("partition_col") or "").lower(),
                columns=int(item.get("columns") or 0))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name}: numeric stats expected") from exc
    return out


@dataclass
class ScanEstimate:
    table: str
    bytes: float
    rows: float
    pruned: bool          # partition pruning applied
    col_ratio: float      # column pruning discount applied

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "bytes": round(self.bytes),
                "rows": round(self.rows), "pruned": self.pruned,
                "col_ratio": round(self.col_ratio, 3)}


@dataclass
class CostCard:
    scans: list[ScanEstimate] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    joins: int = 0
    aggregates: bool = False
    broadcast_joins: int = 0
    scan_bytes: float = 0.0
    shuffle_bytes: float = 0.0
    output_rows: float = 0.0
    memory_peak_bytes: float = 0.0
    core_seconds: float = 0.0
    parallelism: int = 2
    wall_seconds: tuple[float, float] = (0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scans": [s.to_dict() for s in self.scans],
            "missing": list(self.missing),
            "joins": self.joins,
            "aggregates": self.aggregates,
            "broadcast_joins": self.broadcast_joins,
            "scan_bytes": round(self.scan_bytes),
            "shuffle_bytes": round(self.shuffle_bytes),
            "output_rows": round(self.output_rows),
            "memory_peak_bytes": round(self.memory_peak_bytes),
            "core_seconds": round(self.core_seconds, 1),
            "parallelism": self.parallelism,
            "wall_seconds": [round(w, 1) for w in self.wall_seconds],
        }


def _tables_and_filters(sql: str) -> tuple[dict[str, str], str, int,
                                           bool, dict[str, int]]:
    """alias→table, lowered sql, join count, has aggregation,
    selected-column count per alias (0 = star/unknown)."""
    import sqlglot
    from sqlglot import exp

    from seatunnel_agent.common.utils import sql_alias_map

    stmt = sqlglot.parse_one(sql)
    aliases = sql_alias_map(stmt)
    joins = len(list(stmt.find_all(exp.Join)))
    has_agg = bool(stmt.find(exp.Group)
                   or stmt.find(exp.Distinct)
                   or stmt.find(exp.AggFunc))
    selected: dict[str, int] = {}
    select = stmt.find(exp.Select)
    if select and not any(isinstance(e, exp.Star)
                          for e in select.expressions):
        # the physical read set: distinct columns anywhere in the
        # statement (projection, filters, join keys, group by)
        read_cols: dict[str, set[str]] = {}
        for col in stmt.find_all(exp.Column):
            read_cols.setdefault((col.table or "").lower(),
                                 set()).add(col.name.lower())
        selected = {alias: len(names)
                    for alias, names in read_cols.items()}
    return aliases, stmt.sql().lower(), joins, has_agg, selected


def estimate(sql: str, stats: dict[str, TableStats]) -> CostCard:
    if not (sql or "").strip():
        raise ValueError("empty SQL")
    try:
        aliases, lowered, joins, has_agg, selected = \
            _tables_and_filters(sql)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"SQL not parseable: {exc}") from exc
    if not aliases:
        raise ValueError("no tables referenced in the SQL")

    card = CostCard(joins=joins, aggregates=has_agg)
    for alias, table in sorted(set(aliases.items())):
        st = stats.get(table)
        if st is None:
            if table not in card.missing:
                card.missing.append(table)
            continue
        pruned = bool(
            st.partition_col
            and re.search(rf"\b(?:\w+\.)?{re.escape(st.partition_col)}\s*=",
                          lowered))
        col_ratio = 1.0
        n_selected = selected.get(alias, 0) or selected.get("", 0)
        if st.columns and n_selected:
            col_ratio = min(n_selected / st.columns, 1.0)
        factor = (1 / st.partitions if pruned else 1.0) * col_ratio
        scan_bytes = st.bytes * factor
        scan_rows = st.rows * (1 / st.partitions if pruned else 1.0)
        if not any(s.table == table for s in card.scans):
            card.scans.append(ScanEstimate(
                table=table, bytes=scan_bytes, rows=scan_rows,
                pruned=pruned, col_ratio=col_ratio))

    sides = [s.bytes for s in card.scans]  # per-table bytes (join model)
    max_rows = max((s.rows for s in card.scans), default=0.0)
    card.scan_bytes = sum(sides)
    # join shuffle: each join exchanges both sides unless the smaller
    # one broadcasts; aggregation exchanges its input once
    if joins and len(sides) >= 2:
        ordered = sorted(sides)
        for small in ordered[:-1][:joins]:
            if small <= BROADCAST_BYTES:
                card.broadcast_joins += 1
            else:
                card.shuffle_bytes += small + ordered[-1]
    if has_agg:
        card.shuffle_bytes += card.scan_bytes
    card.output_rows = (max_rows / AGG_SHRINK) if has_agg else max_rows

    busiest = max([s.bytes for s in card.scans] + [card.shuffle_bytes],
                  default=0.0)
    card.memory_peak_bytes = busiest / SHUFFLE_PARTITIONS * MEMORY_HEADROOM
    total = card.scan_bytes + card.shuffle_bytes
    card.core_seconds = total / CORE_THROUGHPUT
    gb = card.scan_bytes / (1 << 30)
    card.parallelism = max(2, min(200, int(gb) + 2))
    base = card.core_seconds / card.parallelism
    card.wall_seconds = (base * UNCERTAINTY[0], base * UNCERTAINTY[1])
    return card


def what_if(base: CostCard, sql: str, stats: dict[str, TableStats],
            assumptions: list[tuple[str, str, int]]) -> dict[str, Any]:
    """Re-estimate under assumed partitionings and report the scan delta.

    ``assumptions`` is (table, partition_col, partitions) triples; an
    unknown table or a partition count < 2 raises ValueError rather
    than guessing.
    """
    import dataclasses

    tweaked = dict(stats)
    for table, col, n in assumptions:
        if table not in tweaked:
            raise ValueError(f"table not in the stats inventory: {table!r}")
        if n < 2:
            raise ValueError(f"{table}:{col}: partition count unknown, "
                             "state it explicitly (table:col:N)")
        tweaked[table] = dataclasses.replace(
            tweaked[table], partition_col=col, partitions=n)
    after = estimate(sql, tweaked)
    saved_pct = (round(100 * (1 - after.scan_bytes / base.scan_bytes), 1)
                 if base.scan_bytes else 0.0)
    return {"assumed": [f"{t}:{c}:{n}" for t, c, n in assumptions],
            "base_scan_bytes": round(base.scan_bytes),
            "scan_bytes": round(after.scan_bytes),
            "scan_saved_pct": saved_pct}


def estimate_batch(items: list[tuple[str, str]],
                   stats: dict[str, TableStats]) -> dict[str, Any]:
    """Estimate a (name, sql) workload against one inventory.

    Returns the per-query cards sorted most-expensive first (by
    core-seconds), the totals, and the items the estimator could not
    parse — named, never guessed at.
    """
    cards: list[tuple[str, CostCard]] = []
    skipped: list[str] = []
    for name, sql in items:
        try:
            cards.append((name, estimate(sql, stats)))
        except ValueError as exc:
            skipped.append(f"{name}: {exc}")
    cards.sort(key=lambda nc: (-nc[1].core_seconds, nc[0]))
    return {
        "queries": [{"name": name, **card.to_dict()}
                    for name, card in cards],
        "totals": {
            "scan_bytes": round(sum(c.scan_bytes for _, c in cards)),
            "shuffle_bytes": round(sum(c.shuffle_bytes for _, c in cards)),
            "core_seconds": round(sum(c.core_seconds for _, c in cards), 1),
        },
        "skipped": skipped,
    }


def compare(base: CostCard, rewrite: CostCard) -> dict[str, Any]:
    """Delta card between the original SQL and a rewritten version.

    Positive ``saved_pct`` means the rewrite is cheaper on that axis.
    """
    def pct(before: float, after: float) -> float:
        return round(100 * (1 - after / before), 1) if before else 0.0

    return {
        "base": base.to_dict(),
        "rewrite": rewrite.to_dict(),
        "saved_pct": {
            "scan": pct(base.scan_bytes, rewrite.scan_bytes),
            "shuffle": pct(base.shuffle_bytes, rewrite.shuffle_bytes),
            "memory": pct(base.memory_peak_bytes,
                          rewrite.memory_peak_bytes),
            "core_seconds": pct(base.core_seconds, rewrite.core_seconds),
        },
    }


def parse_assumptions(specs: list[str],
                      stats: dict[str, TableStats]) -> list[tuple[str, str, int]]:
    """"table:col[:N]" specs -> what_if assumption triples.

    When N is omitted the table's declared partition count is used;
    malformed specs raise ValueError (what_if validates the rest).
    """
    out: list[tuple[str, str, int]] = []
    for spec in specs:
        parts = spec.split(":")
        if len(parts) not in (2, 3):
            raise ValueError(
                f"expected table:col[:N], got {spec!r}")
        table, col = parts[0].strip().lower(), parts[1].strip().lower()
        known = stats.get(table)
        n = (int(parts[2]) if len(parts) == 3
             else known.partitions if known else 0)
        out.append((table, col, n))
    return out
