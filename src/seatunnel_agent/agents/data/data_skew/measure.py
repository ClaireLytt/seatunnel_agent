"""Split-key column measurement + candidate ranking (live SQL probes).

Moved verbatim out of splitkey.py, which re-exports the public names.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .probe import (
    HOT_KEY_CONFIRMED,
    HOT_KEY_SUSPECT,
    NULL_CONFIRMED,
    _table_expr,
)

if TYPE_CHECKING:  # pragma: no cover
    from .seatunnel_conf import SourceSpec


class SplitKeyError(ValueError):
    """Config-level failure; ``key`` is the i18n message key, ``arg`` the
    optional {err} detail."""

    def __init__(self, key: str, arg: str = "") -> None:
        super().__init__(key)
        self.key = key
        self.arg = arg


MAX_CANDIDATES = 5

MAX_PARALLEL = 4

NDV_PER_TASK = 4

_CANDIDATE_TYPE_RE = re.compile(
    r"int|serial|number|decimal|numeric|double|float|real|date|time",
    re.IGNORECASE,
)

_APPROX_NDV: dict[str, str] = {
    "sparksql": "approx_count_distinct({col})",
    "clickhouse": "uniq({col})",
    "doris": "ndv({col})",
}

@dataclass
class SplitStat:
    column: str
    total: int = 0
    ndv: int = 0
    null_count: int = 0
    top1_value: str = ""
    top1_count: int = 0
    elapsed_ms: int = 0
    error: str = ""

    @property
    def null_ratio(self) -> float:
        return self.null_count / self.total if self.total else 0.0

    @property
    def top1_ratio(self) -> float:
        return self.top1_count / self.total if self.total else 0.0

    def verdict(self, tasks: int) -> str:
        """'good' | 'suspect' | 'bad' | 'low_ndv' | 'null' | 'error' | 'empty'."""
        if self.error:
            return "error"
        if not self.total:
            return "empty"
        if self.null_ratio >= NULL_CONFIRMED:
            return "null"
        if self.ndv < NDV_PER_TASK * tasks:
            return "low_ndv"
        if self.top1_ratio >= HOT_KEY_CONFIRMED:
            return "bad"
        if self.top1_ratio >= HOT_KEY_SUSPECT:
            return "suspect"
        return "good"


def _ndv_expr(column: str, ds_type: str) -> str:
    tpl = _APPROX_NDV.get(ds_type)
    return tpl.format(col=column) if tpl else f"COUNT(DISTINCT {column})"


def _stats_sql(column: str, table_expr: str, ds_type: str = "") -> str:
    return (
        f"SELECT COUNT(*) AS total, {_ndv_expr(column, ds_type)} AS ndv, "
        f"SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END) AS nulls "
        f"FROM {table_expr}"
    )


def _top1_sql(column: str, table_expr: str) -> str:
    return (
        f"SELECT {column} AS k, COUNT(*) AS cnt FROM {table_expr} "
        f"WHERE {column} IS NOT NULL "
        f"GROUP BY {column} ORDER BY cnt DESC LIMIT 1"
    )


def measure_column(executor, table: str, column: str,
                   ds_type: str = "", sample_pct: int = 0) -> SplitStat:
    """Two bounded scans: totals/NDV/NULLs, then the top-1 non-NULL value."""
    s = SplitStat(column=column)
    expr = _table_expr(table, ds_type, sample_pct)
    try:
        rq = executor.run(_stats_sql(column, expr, ds_type), max_rows=1)
        s.total = int(rq.rows[0][0] or 0)
        s.ndv = int(rq.rows[0][1] or 0)
        s.null_count = int(rq.rows[0][2] or 0)
        s.elapsed_ms += rq.elapsed_ms
        if s.total:
            tq = executor.run(_top1_sql(column, expr), max_rows=1)
            if tq.rows:
                s.top1_value = "NULL" if tq.rows[0][0] is None else str(tq.rows[0][0])
                s.top1_count = int(tq.rows[0][1] or 0)
            s.elapsed_ms += tq.elapsed_ms
    except Exception as exc:  # noqa: BLE001 — per-column failure stays local
        s.error = str(exc)
    return s


def candidate_columns(executor, table: str, exclude: str = "") -> list[str]:
    """Numeric/date columns of *table*, config order, configured key excluded."""
    schema = executor.describe_table(table)
    out: list[str] = []
    for col in schema.columns:
        if col.name.lower() == exclude.lower():
            continue
        if _CANDIDATE_TYPE_RE.search(col.dtype or ""):
            out.append(col.name)
        if len(out) >= MAX_CANDIDATES:
            break
    return out


def measure_columns(executor, table: str, columns: list[str],
                    ds_type: str = "", sample_pct: int = 0) -> list[SplitStat]:
    if not columns:
        return []
    if len(columns) == 1:
        return [measure_column(executor, table, columns[0], ds_type, sample_pct)]
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(columns))) as pool:
        return list(pool.map(
            lambda c: measure_column(executor, table, c, ds_type, sample_pct),
            columns))


_VERDICT_RANK = {"good": 0, "suspect": 1, "low_ndv": 2, "null": 2,
                 "bad": 3, "empty": 4, "error": 5}


def rank_candidates(stats: list[SplitStat], tasks: int) -> list[SplitStat]:
    """Best split key first: verdict class, then top-1 share, then NDV."""
    return sorted(stats, key=lambda s: (
        _VERDICT_RANK.get(s.verdict(tasks), 5), s.top1_ratio, -s.ndv))


# verdicts a split key can ship with
_GOOD_VERDICTS = ("good", "suspect")


def pick_best_key(
    spec: SourceSpec,
    configured: SplitStat | None,
    candidates: list[SplitStat],
) -> SplitStat | None:
    """The key the report recommends: keep a good configured key, else the
    best usable measured candidate; ``None`` when nothing qualifies."""
    tasks = spec.tasks
    if configured is not None and configured.verdict(tasks) in _GOOD_VERDICTS:
        return configured
    for s in rank_candidates(candidates, tasks):
        if s.verdict(tasks) in _GOOD_VERDICTS:
            return s
    return None
