"""Deterministic SQL expansion for metric definitions.

Moved verbatim out of metrics.py, which forwards the public names via a
module __getattr__ (lazy, to avoid an import cycle).
"""

from __future__ import annotations

import re

from .metrics import (
    _BARE_COLUMN_RE,
    _EXPR_KEYWORDS,
    FACT_ALIAS,
    MetricDef,
    MetricError,
    MetricStore,
)
from .partition import TimeRange, pt_value
from .schema import SchemaStore, TableSchema

# ----------------------------------------------------------------------


def _time_filter(
    metric: MetricDef,
    table: TableSchema,
    time_range: TimeRange | None,
    max_partition: str | None,
) -> str | None:
    """WHERE fragment for the metric's time column, or None.

    Partition columns use the conventional yyyyMMdd literal; ordinary date
    columns use ISO yyyy-MM-dd.
    """
    tcol = metric.time_column
    if not tcol:
        return None
    is_partition_col = tcol.lower() in {
        c.name.lower() for c in table.partition_columns
    }
    fmt = pt_value if is_partition_col else (lambda d: d.isoformat())

    if time_range is not None and not time_range.is_empty:
        start, end = time_range.start, time_range.end
        if start and end and start != end:
            return f"{tcol} >= '{fmt(start)}' AND {tcol} <= '{fmt(end)}'"
        d = start or end
        assert d is not None  # guarded by `not time_range.is_empty`
        return f"{tcol} = '{fmt(d)}'"

    if max_partition and is_partition_col:
        return f"{tcol} = '{max_partition}'"

    if is_partition_col:
        raise MetricError(
            f"指标 '{metric.name}' 的时间列 '{tcol}' 是分区列，必须提供时间范围"
            "或 max_partition（可先调用 get_max_partition）"
        )
    return None


# Spans the qualifier must never rewrite: string literals AND backtick-quoted
# identifiers (`t.col` inside backticks would be an invalid identifier).
_PROTECTED_SPAN_RE = re.compile(r"'(?:[^'\\]|\\.)*'|`[^`]*`")


def _map_outside_literals(text: str, fn) -> str:
    """Apply ``fn`` to the segments of ``text`` outside protected spans
    (string literals and backtick-quoted identifiers)."""
    out: list[str] = []
    last = 0
    for m in _PROTECTED_SPAN_RE.finditer(text):
        out.append(fn(text[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(fn(text[last:]))
    return "".join(out)


def _qualify_columns(expr: str, cols: set[str], alias: str) -> str:
    """Prefix bare references to ``cols`` with ``alias.`` (deterministic
    text rewrite: qualified refs, function calls, keywords and string
    literals are left untouched)."""

    def _sub(segment: str) -> str:
        def _repl(m: re.Match) -> str:
            word = m.group(1)
            if word.lower() in cols and word.lower() not in _EXPR_KEYWORDS:
                return f"{alias}.{word}"
            return word
        return _BARE_COLUMN_RE.sub(_repl, segment)

    return _map_outside_literals(expr, _sub)


def dim_output_name(dim: str) -> str:
    """Result-column name of a dimension ('ch.channel_name' -> 'channel_name')."""
    return dim.rsplit(".", 1)[-1]


def _build_additive_sql(
    metric: MetricDef,
    table: TableSchema,
    schema_store: SchemaStore,
    dimensions: list[str],
    time_range: TimeRange | None,
    max_partition: str | None,
    extra_filters: list[str],
) -> str:
    has_joins = bool(metric.joins)
    if has_joins:
        fact_cols = {
            c.name.lower() for c in table.columns + table.partition_columns
        }
        qualify = lambda e: _qualify_columns(e, fact_cols, FACT_ALIAS)
    else:
        qualify = lambda e: e

    conditions: list[str] = []
    tf = _time_filter(metric, table, time_range, max_partition)
    if tf:
        conditions.append(qualify(tf))
    conditions.extend(f"({qualify(f)})" for f in metric.default_filters)
    conditions.extend(f"({qualify(f)})" for f in extra_filters)

    if not has_joins:
        select_items = list(dimensions) + [f"{metric.expression} AS {metric.name}"]
        lines = [
            "SELECT " + ", ".join(select_items),
            f"FROM {table.full_name}",
        ]
        if conditions:
            lines.append("WHERE " + "\n  AND ".join(conditions))
        if dimensions:
            lines.append("GROUP BY " + ", ".join(dimensions))
        return "\n".join(lines)

    # Star-schema form: fact table aliased as FACT_ALIAS, dims may be
    # alias-qualified; result columns keep their bare names so ratio outer
    # queries and breakdowns are alias-agnostic.
    dim_refs = [d if "." in d else f"{FACT_ALIAS}.{d}" for d in dimensions]
    select_items = [
        f"{ref} AS {dim_output_name(d)}"
        for ref, d in zip(dim_refs, dimensions)
    ]
    select_items.append(f"{qualify(metric.expression)} AS {metric.name}")

    lines = [
        "SELECT " + ", ".join(select_items),
        f"FROM {table.full_name} {FACT_ALIAS}",
    ]
    for spec in metric.joins:
        jt = schema_store.get(spec.table)
        j_cols = {c.name.lower() for c in jt.columns} if jt else set()
        on_parts = [
            f"{FACT_ALIAS}.{spec.local_key} = {spec.alias}.{spec.remote_key}"
        ]
        on_parts.extend(
            f"({_qualify_columns(f, j_cols, spec.alias)})" for f in spec.filters
        )
        keyword = "LEFT JOIN" if spec.join_type == "left" else "INNER JOIN"
        lines.append(
            f"{keyword} {spec.table} {spec.alias} ON " + " AND ".join(on_parts)
        )
    if conditions:
        lines.append("WHERE " + "\n  AND ".join(conditions))
    if dim_refs:
        lines.append("GROUP BY " + ", ".join(dim_refs))
    return "\n".join(lines)


def _indent(sql: str, prefix: str = "  ") -> str:
    return "\n".join(prefix + line for line in sql.splitlines())


def ratio_sides(metric: MetricDef, store: MetricStore) -> tuple[MetricDef, MetricDef]:
    """Resolve a ratio metric's numerator/denominator definitions, raising
    :class:`MetricError` when either is missing or itself a ratio."""
    num = store.get(metric.numerator)
    den = store.get(metric.denominator)
    if num is None or den is None or num.is_ratio or den.is_ratio:
        raise MetricError(
            f"ratio 指标 '{metric.name}' 的分子/分母定义无效"
        )
    return num, den


def build_metric_sql(
    metric: MetricDef,
    store: MetricStore,
    schema_store: SchemaStore,
    dimensions: list[str] | None = None,
    time_range: TimeRange | None = None,
    max_partition: str | None = None,
    extra_filters: list[str] | None = None,
) -> str:
    """Expand a metric into SQL. Pure function: identical inputs always
    produce byte-identical SQL. Raises :class:`MetricError` on invalid
    parameters (out-of-whitelist dimension, missing time range, ...).

    The caller MUST still pass the result through ``validate_sql`` before
    execution (double insurance; the agent's execute_sql tool already does).

    v1 limitations (documented in the PRD): a single ``max_partition`` value
    is applied to both sides of a ratio metric; ``extra_filters`` are applied
    to both sides too, so they should only reference columns present in both
    underlying tables.
    """
    dimensions = [d.strip() for d in (dimensions or []) if d.strip()]
    extra_filters = [f.strip() for f in (extra_filters or []) if f.strip()]

    if not metric.is_ratio:
        allowed = {d.lower() for d in metric.dimensions}
        for dim in dimensions:
            if dim.lower() not in allowed:
                raise MetricError(
                    f"维度 '{dim}' 不在指标 '{metric.name}' 的允许维度中"
                    f"（允许: {', '.join(metric.dimensions) or '无'}）"
                )
        table = schema_store.get(metric.table)
        if table is None:
            raise MetricError(f"表 '{metric.table}' 不在 schema 白名单中")
        return _build_additive_sql(
            metric, table, schema_store, dimensions, time_range, max_partition,
            extra_filters,
        )

    num, den = ratio_sides(metric, store)
    allowed = {d.lower() for d in num.dimensions} & {
        d.lower() for d in den.dimensions
    }
    for dim in dimensions:
        if dim.lower() not in allowed:
            raise MetricError(
                f"维度 '{dim}' 必须同时在分子 '{num.name}' 和分母 "
                f"'{den.name}' 的允许维度中"
            )

    num_sql = build_metric_sql(
        num, store, schema_store, dimensions, time_range, max_partition,
        extra_filters,
    )
    den_sql = build_metric_sql(
        den, store, schema_store, dimensions, time_range, max_partition,
        extra_filters,
    )

    ratio_expr = (
        f"num.{num.name} * 1.0 / NULLIF(den.{den.name}, 0) AS {metric.name}"
    )
    if not dimensions:
        return "\n".join([
            f"SELECT {ratio_expr}",
            "FROM (",
            _indent(num_sql),
            ") num",
            "CROSS JOIN (",
            _indent(den_sql),
            ") den",
        ])

    dim_outs = [dim_output_name(d) for d in dimensions]
    dim_items = ", ".join(f"den.{d}" for d in dim_outs)
    on_items = " AND ".join(f"den.{d} = num.{d}" for d in dim_outs)
    return "\n".join([
        f"SELECT {dim_items}, {ratio_expr}",
        "FROM (",
        _indent(den_sql),
        ") den",
        "LEFT JOIN (",
        _indent(num_sql),
        ") num ON " + on_items,
    ])


def build_metric_series_sql(
    metric: MetricDef,
    store: MetricStore,
    schema_store: SchemaStore,
    time_range: TimeRange,
) -> str:
    """Expand a metric into a DAILY SERIES SQL (one row per time-column
    value, ordered ascending). Pure function like :func:`build_metric_sql`;
    used by the forecast tool. Raises :class:`MetricError` when the metric
    (or either side of a ratio) has no ``time_column``.
    """
    def _inner(m: MetricDef) -> str:
        """Additive daily series: one row per time-column value."""
        if not m.time_column:
            raise MetricError(
                f"metric '{m.name}' has no time_column; "
                "a daily series cannot be built"
            )
        table = schema_store.get(m.table)
        if table is None:
            raise MetricError(f"table '{m.table}' is not whitelisted")
        return _build_additive_sql(
            m, table, schema_store, [m.time_column], time_range, None, [],
        )

    if not metric.is_ratio:
        return _inner(metric) + f"\nORDER BY {dim_output_name(metric.time_column)}"

    num, den = ratio_sides(metric, store)
    num_sql, den_sql = _inner(num), _inner(den)  # validates time columns
    n_day = dim_output_name(num.time_column)
    d_day = dim_output_name(den.time_column)

    # COALESCE the numerator: a LEFT JOIN miss (day with denominator rows
    # but no numerator rows) is a true rate of 0, not an undefined day —
    # only a NULL denominator leaves the ratio NULL.
    ratio_expr = (
        f"COALESCE(num.{num.name}, 0) * 1.0 "
        f"/ NULLIF(den.{den.name}, 0) AS {metric.name}"
    )
    return "\n".join([
        f"SELECT den.{d_day} AS {d_day}, {ratio_expr}",
        "FROM (",
        _indent(den_sql),
        ") den",
        "LEFT JOIN (",
        _indent(num_sql),
        f") num ON num.{n_day} = den.{d_day}",
        f"ORDER BY den.{d_day}",
    ])
