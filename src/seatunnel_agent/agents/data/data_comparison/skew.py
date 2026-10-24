"""Data-skew comparison: top-N frequency SQL, gini/top-1 metrics, verdicts (BB)."""

from __future__ import annotations

import math

from .models import SkewBucket, SkewItem, SkewResult
from .sqlbase import (
    GINI_MISMATCH_THRESHOLD,
    GINI_SKEW_THRESHOLD,
    TOP1_MISMATCH_PP,
    TOP1_SKEW_THRESHOLD,
    _where_clause,
    cast_to_string,
    quote_identifier,
)

# ---------------------------------------------------------------------------
# Data skew analysis  (BB)
# ---------------------------------------------------------------------------

def build_skew_sql(
    table_name: str, column: str, where: str = "", top_n: int = 20,
    ds_type: str = "mysql",
) -> str:
    """Build SQL to get top-N value frequencies for one column."""
    qc = quote_identifier(column, ds_type)
    qt = quote_identifier(table_name, ds_type)
    if top_n > 0 and ds_type == "sqlserver":
        top_clause = f"TOP {int(top_n)} "
    else:
        top_clause = ""
    sql = (
        f"SELECT {top_clause}{cast_to_string(qc, ds_type)} AS val, COUNT(*) AS cnt"
        f"\n  FROM {qt}{_where_clause(where)}"
        f"\n GROUP BY {qc}"
        f"\n ORDER BY cnt DESC"
    )
    if top_n > 0 and ds_type != "sqlserver":
        sql += f"\n LIMIT {top_n}"
    return sql


def compute_skew_metrics(counts: list[int]) -> tuple[float, float, float]:
    """Return (gini, cv, top1_pct) from a list of frequency counts.

    - gini: 0 = uniform, 1 = all in one value
    - cv: coefficient of variation (std/mean)
    - top1_pct: percentage held by largest value
    """
    if not counts:
        return 0.0, 0.0, 0.0
    total = sum(counts)
    if total == 0:
        return 0.0, 0.0, 0.0
    n = len(counts)
    if n == 1:
        return 0.0, 0.0, 100.0

    # Gini coefficient
    sorted_c = sorted(counts)
    cum = 0.0
    weighted_sum = 0.0
    for i, c in enumerate(sorted_c):
        cum += c
        weighted_sum += (2 * (i + 1) - n - 1) * c
    gini = weighted_sum / (n * total) if total else 0.0
    gini = max(0.0, min(1.0, gini))

    # CV
    mean = total / n
    variance = sum((c - mean) ** 2 for c in counts) / n
    std = math.sqrt(variance)
    cv = std / mean if mean else 0.0

    # Top-1 concentration
    top1 = max(counts) / total * 100

    return round(gini, 4), round(cv, 4), round(top1, 2)


def compare_skew(
    table_a: str, table_b: str, column: str,
    rows_a: list[tuple], total_a: int,
    rows_b: list[tuple], total_b: int,
    top_n: int = 20,
) -> SkewItem:
    """Compare skew for one column between two tables."""
    counts_a = [int(r[1]) for r in rows_a if len(r) >= 2]
    counts_b = [int(r[1]) for r in rows_b if len(r) >= 2]

    gini_a, cv_a, top1_a = compute_skew_metrics(counts_a)
    gini_b, cv_b, top1_b = compute_skew_metrics(counts_b)

    # Merge buckets from both sides
    map_a: dict[str, int] = {}
    for r in rows_a:
        if len(r) >= 2:
            map_a[str(r[0])] = int(r[1])
    map_b: dict[str, int] = {}
    for r in rows_b:
        if len(r) >= 2:
            map_b[str(r[0])] = int(r[1])

    all_vals: list[str] = []
    seen: set[str] = set()
    for r in rows_a:
        v = str(r[0]) if len(r) >= 1 else ""
        if v not in seen:
            all_vals.append(v)
            seen.add(v)
    for r in rows_b:
        v = str(r[0]) if len(r) >= 1 else ""
        if v not in seen:
            all_vals.append(v)
            seen.add(v)

    buckets: list[SkewBucket] = []
    for v in all_vals[:top_n]:
        ca = map_a.get(v, 0)
        cb = map_b.get(v, 0)
        buckets.append(SkewBucket(
            value=v,
            count_a=ca, count_b=cb,
            pct_a=round(ca / total_a * 100, 2) if total_a else 0.0,
            pct_b=round(cb / total_b * 100, 2) if total_b else 0.0,
        ))

    return SkewItem(
        column=column,
        gini_a=gini_a, gini_b=gini_b,
        cv_a=cv_a, cv_b=cv_b,
        top1_pct_a=top1_a, top1_pct_b=top1_b,
        ndv_a=len(map_a), ndv_b=len(map_b),
        buckets=buckets,
    )


def skew_side_verdict(result: SkewResult) -> tuple[str, list[str]]:
    """Qualify the measured skew: sync symptom or business fact.

    Returns ``(verdict, columns)`` where verdict is:
    - ``"mismatch"``: A and B disagree on a column's distribution — when B
      is synced from A this points at the sync pipeline (split/filter
      logic), so fix the data before tuning any compute.
    - ``"both_skewed"``: both sides skew the same way — a business fact
      (hot customer / default value); protect the downstream compute.
    - ``"ok"``: nothing notable.
    Mismatch wins over both_skewed when both are present.
    """
    if not result.items or not result.total_a or not result.total_b:
        return "ok", []
    mismatch: list[str] = []
    both: list[str] = []
    for it in result.items:
        if (abs(it.gini_a - it.gini_b) > GINI_MISMATCH_THRESHOLD
                or abs(it.top1_pct_a - it.top1_pct_b) > TOP1_MISMATCH_PP):
            mismatch.append(it.column)
        elif ((it.gini_a > GINI_SKEW_THRESHOLD and it.gini_b > GINI_SKEW_THRESHOLD)
              or (it.top1_pct_a > TOP1_SKEW_THRESHOLD
                  and it.top1_pct_b > TOP1_SKEW_THRESHOLD)):
            both.append(it.column)
    if mismatch:
        return "mismatch", mismatch
    if both:
        return "both_skewed", both
    return "ok", []


