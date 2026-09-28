"""Tool definitions and execution for the Text2SQL agent.

The runtime object carries shared state (schema store, executor, last
result) across tool calls within one agent session.
"""

from __future__ import annotations

import difflib
import json
import re
import threading
from dataclasses import dataclass, field
from typing import Any

from .cache import SqlResultCache
from .executor import (
    PARTITION_ENGINES,
    DatabaseConfig,
    DatabaseExecutor,
    QueryResult,
    create_executor,
)
from .exporter import export_csv
from .matcher import match_tables
from .metrics import MetricError, MetricStore, build_metric_sql, parse_time_range
from .partition import classify_table, has_partition_filter
from .qlog import QueryLogger
from .schema import SchemaStore
from .quality import check_quality
from .validator import ValidationResult, enforce_limit, validate_sql

_DB_CONN_RE = re.compile(
    r"(?:jdbc:[^\s]+|(?:\d{1,3}\.){3}\d{1,3}:\d+|"
    r"password\s*=\s*\S+|user\s*=\s*\S+|"
    r"host\s*=\s*\S+|port\s*=\s*\d+)",
    re.IGNORECASE,
)


def _sanitize_db_error(msg: str) -> str:
    """Strip connection details (host, port, credentials) from DB errors."""
    return _DB_CONN_RE.sub("[REDACTED]", msg)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "match_tables",
        "description": (
            "Rank candidate tables for a natural-language question by keyword "
            "and comment relevance. Returns top tables with scores, comments "
            "and which keywords matched. Call this first unless the user "
            "already named an exact table."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's natural-language question",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_table_schema",
        "description": (
            "Get the full schema of a table: columns with types and Chinese "
            "comments, partition columns, and table type "
            "(incremental/_di/_hi/_ri, full/_df/_hf, or other). "
            "Always call before writing SQL against a table."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Full table name, e.g. zz.dwm_scm_detail_di",
                },
            },
            "required": ["table"],
        },
    },
    {
        "name": "get_max_partition",
        "description": (
            "Return the latest partition value (e.g. 20260313) of a "
            "partitioned table via SHOW PARTITIONS (cached). Use when the "
            "user gave no time range, so the query can still prune partitions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Full table name, e.g. zz.dwm_scm_detail_di",
                },
            },
            "required": ["table"],
        },
    },
    {
        "name": "match_metrics",
        "description": (
            "Rank defined business metrics (指标) matching the question. "
            "Returns each metric's caliber description (口径), source table, "
            "allowed dimensions, unit and owner. MUST be called first whenever "
            "the question involves a business metric; if a metric matches, use "
            "build_metric_sql instead of hand-writing the aggregation. Also "
            "sufficient by itself to answer caliber questions ('X的口径是什么') "
            "— do NOT execute SQL for those."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's natural-language question",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "build_metric_sql",
        "description": (
            "Deterministically expand a defined metric into SQL (same inputs "
            "always yield identical SQL — the caliber-consistency guarantee). "
            "Returns the SQL only; run it with execute_sql afterwards. "
            "Dimensions must come from the metric's allowed list. For "
            "partitioned time columns provide a date range or max_partition "
            "(from get_max_partition)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "description": "Metric name as returned by match_metrics",
                },
                "dimensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Group-by dimension columns (allowed list only)",
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date, YYYY-MM-DD or yyyyMMdd",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date (inclusive), YYYY-MM-DD or yyyyMMdd",
                },
                "max_partition": {
                    "type": "string",
                    "description": (
                        "Latest partition value to use when no date range was "
                        "given (from get_max_partition)"
                    ),
                },
                "extra_filters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Additional SQL boolean conditions, e.g. "
                        "\"channel = 'app'\""
                    ),
                },
            },
            "required": ["metric"],
        },
    },
    {
        "name": "run_attribution",
        "description": (
            "Attribute a defined metric's change between two periods (为什么"
            "涨/跌): deterministic totals comparison + per-dimension drill-down "
            "with contribution decomposition (contributions sum exactly to the "
            "total change rate). Requires TWO explicit date ranges — compute "
            "the comparison period yourself (环比 = preceding period of equal "
            "length; 同比 = same period last year). Omit 'dimension' to "
            "auto-explore all allowed dimensions and pick the most explanatory "
            "one. Ratio metrics are decomposed into numerator/denominator "
            "attributions automatically. Costs 2 + 2×dimensions SQL queries — "
            "call it ONCE per question. The result table is shown to the user "
            "automatically (waterfall chart included)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "description": "Metric name as returned by match_metrics",
                },
                "curr_start": {
                    "type": "string",
                    "description": "Current period start, YYYY-MM-DD or yyyyMMdd",
                },
                "curr_end": {
                    "type": "string",
                    "description": "Current period end (inclusive; defaults to curr_start)",
                },
                "prev_start": {
                    "type": "string",
                    "description": "Comparison period start",
                },
                "prev_end": {
                    "type": "string",
                    "description": "Comparison period end (inclusive; defaults to prev_start)",
                },
                "dimension": {
                    "type": "string",
                    "description": "Drill down on this single dimension only (optional)",
                },
                "extra_filters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional SQL boolean conditions applied to both periods",
                },
            },
            "required": ["metric", "curr_start", "prev_start"],
        },
    },
    {
        "name": "execute_sql",
        "description": (
            "Validate and execute a SELECT statement on the connected database. "
            "Rejects non-SELECT statements and non-whitelisted tables; enforces "
            "a row LIMIT. Returns columns, preview rows, row count and elapsed "
            "time. A CSV download link is shown automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SELECT statement to run",
                },
                "user_query": {
                    "type": "string",
                    "description": "Original user question (for the query log)",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "name": "explain_sql",
        "description": (
            "Run EXPLAIN on a SELECT statement to preview the execution plan "
            "before running it. Useful for checking whether a query will cause "
            "a full table scan or estimating cost. Not supported on SQL Server."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SELECT statement to explain",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "name": "get_result_page",
        "description": (
            "Return a specific page of the most recent query result. "
            "Use this to browse large result sets beyond the initial preview."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "integer",
                    "description": "Page number (1-based)",
                },
                "page_size": {
                    "type": "integer",
                    "description": "Rows per page (default 50, max 200)",
                },
            },
            "required": ["page"],
        },
    },
]


_PREVIEW_ROWS = 20


@dataclass
class Text2SQLRuntime:
    """Shared state for one Text2SQL session."""

    store: SchemaStore
    metrics: MetricStore | None = None
    ds_type: str = "hive"
    db_config: DatabaseConfig | None = None
    source: str = "ui"  # audit tag for qlog: ui / api / mcp / subscription
    logger: QueryLogger = field(default_factory=QueryLogger)
    default_limit: int = 1000
    last_result: QueryResult | None = None
    prev_result: QueryResult | None = None
    last_sql: str = ""
    prev_sql: str = ""
    sql_retries: int = 0
    max_sql_retries: int = 3
    cache: SqlResultCache = field(default_factory=SqlResultCache)
    _executor: DatabaseExecutor | None = None
    _executor_lock: threading.Lock = field(default_factory=threading.Lock)
    _retriever: Any = field(default=None, repr=False)

    @property
    def retriever(self):
        """Hybrid retriever, rebuilt whenever the schema store is swapped
        (table-whitelist filtering replaces the store object)."""
        from .retrieval import HybridRetriever
        if self._retriever is None or self._retriever.store is not self.store:
            self._retriever = HybridRetriever(self.store)
        return self._retriever

    @property
    def executor(self) -> DatabaseExecutor:
        if self._executor is None:
            with self._executor_lock:
                if self._executor is None:
                    if self.db_config is None:
                        raise RuntimeError(
                            "Database connection is not configured. "
                            "Fill in the connection fields in the UI or set "
                            "the corresponding environment variables."
                        )
                    if not self.db_config.host and self.db_config.ds_type != "sqlite":
                        raise RuntimeError(
                            "Database connection is not configured. "
                            "Fill in the connection fields in the UI or set "
                            "the corresponding environment variables."
                        )
                    self._executor = create_executor(self.db_config)
        return self._executor


def _tool_match_tables(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    query = inp.get("query", "")
    try:
        matches = rt.retriever.rank(query, top_n=5)
    except Exception:  # retrieval must never break the tool — degrade
        matches = match_tables(query, rt.store, top_n=5)
    return {
        "candidates": [
            {
                "table": m.table.full_name,
                "comment": m.table.comment,
                "score": round(m.score, 2),
                "table_type": m.table.table_type,
                "name_hits": m.name_hits,
                "comment_hits": m.comment_hits[:10],
                "matched_columns": list(dict.fromkeys(m.column_hits))[:15],
            }
            for m in matches
        ],
        "count": len(matches),
    }


def _tool_get_table_schema(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    name = inp.get("table", "")
    table = rt.store.get(name)
    if table is None:
        return {"error": f"Table '{name}' is not registered in the schema whitelist"}
    return {
        "table": table.full_name,
        "comment": table.comment,
        "table_type": table.table_type,
        "partitioned": table.is_partitioned,
        "partition_columns": [
            {"name": c.name, "type": c.dtype, "comment": c.comment}
            for c in table.partition_columns
        ],
        "columns": [
            {"name": c.name, "type": c.dtype, "comment": c.comment}
            for c in table.columns
        ],
    }


def _tool_get_max_partition(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    if rt.ds_type not in PARTITION_ENGINES:
        return {"error": f"Partition queries are not supported for {rt.ds_type}"}
    name = inp.get("table", "")
    table = rt.store.get(name)
    if table is None:
        return {"error": f"Table '{name}' is not registered in the schema whitelist"}
    if not table.is_partitioned or not table.partition_columns:
        return {"error": f"Table '{name}' is not partitioned"}
    try:
        value = rt.executor.get_max_partition(table.full_name)
    except Exception as exc:
        return {"error": _sanitize_db_error(str(exc))}
    return {
        "table": table.full_name,
        "partition_column": table.partition_columns[0].name,
        "max_partition": value,
        "table_type": classify_table(table.name),
    }


def _metric_payload(m: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": m.name,
        "display_name": m.display_name,
        "description": m.description,
        "type": m.metric_type,
        "unit": m.unit,
        "owner": m.owner,
    }
    if m.is_ratio:
        payload["numerator"] = m.numerator
        payload["denominator"] = m.denominator
    else:
        payload["table"] = m.table
        payload["expression"] = m.expression
        payload["time_column"] = m.time_column
        payload["dimensions"] = list(m.dimensions)
        payload["default_filters"] = list(m.default_filters)
    return payload


def _tool_match_metrics(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    if rt.metrics is None or len(rt.metrics) == 0:
        return {
            "candidates": [],
            "count": 0,
            "note": (
                "No metric definitions loaded (metrics.yaml). Fall back to "
                "match_tables and write the aggregation yourself."
            ),
        }
    query = inp.get("query", "")
    matches = rt.metrics.match(query, top_n=5)
    return {
        "candidates": [
            {**_metric_payload(r.metric), "score": round(r.score, 2), "hits": r.hits}
            for r in matches
        ],
        "count": len(matches),
    }


def _tool_build_metric_sql(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    if rt.metrics is None or len(rt.metrics) == 0:
        return {"error": "No metric definitions loaded (metrics.yaml)"}
    name = str(inp.get("metric", "")).strip()
    metric = rt.metrics.get(name)
    if metric is None:
        known = ", ".join(m.name for m in rt.metrics.metrics)
        return {"error": f"Metric '{name}' is not defined. Known metrics: {known}"}

    try:
        time_range = parse_time_range(
            str(inp.get("start_date", "") or ""),
            str(inp.get("end_date", "") or ""),
        )
        sql = build_metric_sql(
            metric,
            rt.metrics,
            rt.store,
            dimensions=inp.get("dimensions") or [],
            time_range=time_range,
            max_partition=str(inp.get("max_partition", "") or "").strip() or None,
            extra_filters=inp.get("extra_filters") or [],
        )
    except MetricError as exc:
        return {"error": str(exc)}
    return {
        "success": True,
        "metric": _metric_payload(metric),
        "sql": sql,
        "note": "Run this SQL with execute_sql. Do not edit the aggregation.",
    }


def _attribution_execute(rt: Text2SQLRuntime, user_query: str, metric_name: str = ""):
    """Build the validated/cached/logged execute_fn for run_attribution."""

    def _check_truncated(result: QueryResult) -> None:
        # enforce_limit trims at the SQL level, so the executor never sees
        # the overflow — a row count AT the limit means the drill-down was
        # (or may have been) cut off, and contributions would silently stop
        # summing to the total change rate.
        if result.truncated or result.row_count >= rt.default_limit:
            raise MetricError(
                f"维度基数过大：下钻结果达到 {rt.default_limit} 行上限，"
                "贡献分解将不完整。请指定低基数维度（dimension 参数）重试。"
            )

    def _execute(sql: str) -> tuple[list[str], list[tuple]]:
        validation = validate_sql(sql, rt.store)
        if not validation.ok:
            raise MetricError("SQL rejected: " + "; ".join(validation.errors))
        final_sql = enforce_limit(sql, default_limit=rt.default_limit, dialect=rt.ds_type)
        cached = rt.cache.get(final_sql, rt.ds_type)
        if cached is not None:
            _check_truncated(cached)
            return cached.columns, list(cached.rows)
        result = rt.executor.run(final_sql, max_rows=rt.default_limit)
        rt.cache.put(final_sql, rt.ds_type, result)
        rt.logger.log(
            user_query=user_query, generated_sql=final_sql, status="success",
            matched_tables=validation.tables,
            exec_time_ms=result.elapsed_ms, row_count=result.row_count,
            extra={"source": rt.source, "metric": metric_name, "kind": "attribution"},
        )
        _check_truncated(result)
        return result.columns, list(result.rows)

    return _execute


def _run_one_attribution(
    inp: dict[str, Any], rt: Text2SQLRuntime, metric: Any,
) -> "Any":
    from .attribution import run_attribution
    from .metrics import parse_time_range

    curr_range = parse_time_range(
        str(inp.get("curr_start", "") or ""), str(inp.get("curr_end", "") or ""),
    )
    prev_range = parse_time_range(
        str(inp.get("prev_start", "") or ""), str(inp.get("prev_end", "") or ""),
    )
    if curr_range is None or prev_range is None:
        raise MetricError("归因分析必须提供 curr_start 和 prev_start")
    dim = str(inp.get("dimension", "") or "").strip()
    return run_attribution(
        metric, rt.metrics, rt.store,
        _attribution_execute(rt, inp.get("user_query", ""), metric.name),
        curr_range=curr_range,
        prev_range=prev_range,
        dimensions=[dim] if dim else None,
        extra_filters=inp.get("extra_filters") or [],
    )


def _publish_breakdown(rt: Text2SQLRuntime, result: Any) -> None:
    """Expose the best dimension's breakdown as the last result so the
    existing UI machinery (table, waterfall chart, CSV) picks it up."""
    from .attribution import breakdown_table

    best = next(
        (b for b in result.dimensions if b.dimension == result.best_dimension),
        None,
    )
    if best is None or not best.rows:
        return
    columns, rows = breakdown_table(best)
    rt.prev_result = rt.last_result
    rt.prev_sql = rt.last_sql
    rt.last_result = QueryResult(
        columns=columns, rows=rows, row_count=len(rows),
        truncated=False, elapsed_ms=0,
    )
    if result.sqls:
        rt.last_sql = result.sqls[-1]


def _tool_run_attribution(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    from .attribution import attribution_to_dict

    if rt.metrics is None or len(rt.metrics) == 0:
        return {"error": "No metric definitions loaded (metrics.yaml)"}
    name = str(inp.get("metric", "")).strip()
    metric = rt.metrics.get(name)
    if metric is None:
        known = ", ".join(m.name for m in rt.metrics.metrics)
        return {"error": f"Metric '{name}' is not defined. Known metrics: {known}"}

    try:
        if metric.is_ratio:
            num = rt.metrics.get(metric.numerator)
            den = rt.metrics.get(metric.denominator)
            if num is None or den is None:
                return {"error": f"ratio 指标 '{name}' 的分子/分母定义无效"}
            num_res = _run_one_attribution(inp, rt, num)
            den_res = _run_one_attribution(inp, rt, den)
            _publish_breakdown(rt, num_res)

            def _ratio(n: float, d: float) -> float | None:
                return n / d if d else None

            prev_ratio = _ratio(num_res.prev_total, den_res.prev_total)
            curr_ratio = _ratio(num_res.curr_total, den_res.curr_total)
            return {
                "success": True,
                "metric": metric.name,
                "type": "ratio",
                "prev_ratio": round(prev_ratio, 6) if prev_ratio is not None else None,
                "curr_ratio": round(curr_ratio, 6) if curr_ratio is not None else None,
                "numerator": attribution_to_dict(num_res),
                "denominator": attribution_to_dict(den_res),
                "note": (
                    "v1 boundary: ratio metrics are decomposed into separate "
                    "numerator/denominator attributions (no two-factor split). "
                    "Present both movements side by side."
                ),
            }

        result = _run_one_attribution(inp, rt, metric)
        _publish_breakdown(rt, result)
        return {"success": True, "type": "additive", **attribution_to_dict(result)}
    except MetricError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"Attribution failed: {_sanitize_db_error(str(exc))}"}


def _build_sql_error(rt: Text2SQLRuntime, error_msg: str, **extra: Any) -> dict[str, Any]:
    """Increment retry counter and build a structured error response."""
    rt.sql_retries += 1
    error_type, retry_hint = classify_error(error_msg)
    err: dict[str, Any] = {
        "error": error_msg,
        "error_type": error_type,
        "retry_hint": retry_hint,
        "attempt": rt.sql_retries,
        **extra,
    }
    if rt.sql_retries >= rt.max_sql_retries:
        err["max_retries_reached"] = True
    return err


def _log_and_reject(
    rt: Text2SQLRuntime, user_query: str, sql: str,
    tables: list[str], error_msg: str, status: str = "rejected",
) -> dict[str, Any]:
    """Log a failed SQL attempt and return a structured error."""
    rt.logger.log(
        user_query=user_query, generated_sql=sql, status=status,
        matched_tables=tables, error=error_msg,
        extra={"source": rt.source},
    )
    extra: dict[str, Any] = {"sql": sql} if status == "error" else {}
    return _build_sql_error(rt, error_msg, **extra)


def _check_partition_filters(sql: str, validation: ValidationResult, rt: Text2SQLRuntime) -> str | None:
    """Return an error message if any partitioned table lacks a partition filter."""
    if rt.ds_type not in PARTITION_ENGINES:
        return None
    missing = []
    for tname in validation.tables:
        table = rt.store.get(tname)
        if table and table.is_partitioned:
            pcol = table.partition_columns[0].name
            if not has_partition_filter(sql, pcol):
                missing.append(f"{table.full_name} (partition column: {pcol})")
    if missing:
        return (
            "Partitioned table(s) missing partition filter: "
            + ", ".join(missing)
            + ". Add a WHERE condition on the partition column "
            "(use get_max_partition if no time range was given)."
        )
    return None


def _build_success(
    result: QueryResult, sql: str,
    validation: ValidationResult, **extra: Any,
) -> dict[str, Any]:
    """Build a structured success response for execute_sql."""
    out: dict[str, Any] = {
        "success": True,
        "sql": sql,
        "columns": result.columns,
        "preview_rows": [list(r) for r in result.rows[:_PREVIEW_ROWS]],
        "row_count": result.row_count,
        "truncated": result.truncated,
        "elapsed_ms": result.elapsed_ms,
        **extra,
    }
    if validation.column_warnings:
        out["column_warnings"] = validation.column_warnings
    report = check_quality(result.columns, result.rows)
    if report.has_warnings:
        out["quality_warnings"] = [
            {"column": w.column, "warning_type": w.warning_type, "detail": w.detail}
            for w in report.warnings
        ]
    return out


def _tool_execute_sql(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    sql = inp.get("sql", "")
    user_query = inp.get("user_query", "")

    validation = validate_sql(sql, rt.store)
    if not validation.ok:
        return _log_and_reject(
            rt, user_query, sql, validation.tables,
            "SQL rejected: " + "; ".join(validation.errors),
        )

    partition_err = _check_partition_filters(sql, validation, rt)
    if partition_err:
        return _log_and_reject(rt, user_query, sql, validation.tables, partition_err)

    final_sql = enforce_limit(sql, default_limit=rt.default_limit, dialect=rt.ds_type)

    cached = rt.cache.get(final_sql, rt.ds_type)
    if cached is not None:
        rt.sql_retries = 0
        rt.prev_result = rt.last_result
        rt.prev_sql = rt.last_sql
        rt.last_result = cached
        rt.last_sql = final_sql
        rt.logger.log(
            user_query=user_query, generated_sql=final_sql, status="cache_hit",
            matched_tables=validation.tables,
            exec_time_ms=0, row_count=cached.row_count,
            extra={"source": rt.source},
        )
        return _build_success(cached, final_sql, validation, cached=True, elapsed_ms=0)

    try:
        result = rt.executor.run(final_sql, max_rows=rt.default_limit)
    except Exception as exc:
        err = _log_and_reject(
            rt, user_query, final_sql, validation.tables,
            f"Execution failed: {_sanitize_db_error(str(exc))}", status="error",
        )
        suggestion = _suggest_column(str(exc), rt)
        if suggestion:
            err["suggestion"] = suggestion
        return err

    rt.sql_retries = 0
    rt.prev_result = rt.last_result
    rt.prev_sql = rt.last_sql
    rt.last_result = result
    rt.last_sql = final_sql
    rt.cache.put(final_sql, rt.ds_type, result)
    rt.logger.log(
        user_query=user_query, generated_sql=final_sql, status="success",
        matched_tables=validation.tables,
        exec_time_ms=result.elapsed_ms, row_count=result.row_count,
        extra={"source": rt.source},
    )
    out = _build_success(result, final_sql, validation)
    if rt.prev_result is not None:
        from .differ import diff_results
        diff = diff_results(
            rt.prev_result.columns, rt.prev_result.rows,
            result.columns, result.rows,
        )
        if diff.has_changes:
            out["diff"] = {
                "added_count": len(diff.added_rows),
                "removed_count": len(diff.removed_rows),
                "cols_added": diff.columns_added,
                "cols_removed": diff.columns_removed,
                "old_count": diff.old_count,
                "new_count": diff.new_count,
            }
    return out


_EXPLAIN_UNSUPPORTED = frozenset({"sqlserver"})


def _tool_explain_sql(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    sql = inp.get("sql", "").strip()
    if not sql:
        return {"error": "No SQL provided"}
    if rt.ds_type in _EXPLAIN_UNSUPPORTED:
        return {"error": f"EXPLAIN is not supported for {rt.ds_type}"}

    validation = validate_sql(sql, rt.store)
    if not validation.ok:
        return {"error": "SQL rejected: " + "; ".join(validation.errors)}

    try:
        result = rt.executor.run(f"EXPLAIN {sql}", max_rows=200)
    except Exception as exc:
        return {"error": f"EXPLAIN failed: {_sanitize_db_error(str(exc))}"}

    plan_lines = []
    for row in result.rows:
        plan_lines.append(" | ".join(str(v) for v in row))
    return {
        "success": True,
        "sql": sql,
        "plan": "\n".join(plan_lines),
        "columns": result.columns,
    }


_COL_NOT_FOUND_RE = re.compile(
    r"(?:cannot resolve|column not found|unknown column|no such column"
    r"|does not exist|invalid column name|missing columns?)"
    r"[:\s]*['\"`]?([\w.]+)['\"`]?",
    re.IGNORECASE,
)

_SYNTAX_ERR_RE = re.compile(
    r"(?:syntax error|parse error|unexpected token|mismatched input"
    r"|extraneous input|no viable alternative|line \d+:\d+)",
    re.IGNORECASE,
)

_TYPE_ERR_RE = re.compile(
    r"(?:type mismatch|cannot cast|cannot convert|incompatible types"
    r"|invalid input syntax for type|conversion failed"
    r"|data type mismatch|operand type clash)",
    re.IGNORECASE,
)


def classify_error(error_msg: str) -> tuple[str, str]:
    """Classify a SQL execution error and return (error_type, retry_hint)."""
    if _COL_NOT_FOUND_RE.search(error_msg):
        return (
            "column_not_found",
            "Verify column names with get_table_schema; check the suggestion field.",
        )
    if _SYNTAX_ERR_RE.search(error_msg):
        return (
            "syntax_error",
            "Check dialect-specific syntax: date functions, string quoting, JOIN clauses."
            " In Hive, non-ASCII column aliases (Chinese etc.) MUST use backticks: AS `别名`.",
        )
    if _TYPE_ERR_RE.search(error_msg):
        return (
            "type_mismatch",
            "Wrap the expression in CAST() or use the dialect's conversion function.",
        )
    return (
        "execution_error",
        "Read the error details and adjust the query.",
    )


def _suggest_column(error_msg: str, rt: Text2SQLRuntime) -> str | None:
    """If the error names a missing column, suggest the closest match."""
    m = _COL_NOT_FOUND_RE.search(error_msg)
    if not m:
        return None
    raw = m.group(1)
    bad_col = raw.rsplit(".", 1)[-1].lower()
    seen: set[str] = set()
    all_cols: list[str] = []
    for tname in rt.store.table_names:
        table = rt.store.get(tname)
        if table:
            for c in table.columns + table.partition_columns:
                low = c.name.lower()
                if low not in seen:
                    seen.add(low)
                    all_cols.append(low)
    matches = difflib.get_close_matches(bad_col, all_cols, n=3, cutoff=0.6)
    if matches:
        return f"Did you mean: {', '.join(matches)}?"
    return None


def _tool_get_result_page(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    if rt.last_result is None:
        return {"error": "No query result available. Run execute_sql first."}
    page = inp.get("page", 1)
    page_size = min(inp.get("page_size", 50), 200)
    if page < 1:
        page = 1
    total = rt.last_result.row_count
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = rt.last_result.rows[start:end]
    return {
        "success": True,
        "columns": rt.last_result.columns,
        "rows": [list(r) for r in page_rows],
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "total_rows": total,
    }


def _tool_export_csv(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    if rt.last_result is None:
        return {"error": "No query result to export. Run execute_sql first."}
    try:
        path = export_csv(
            rt.last_result.columns,
            rt.last_result.rows,
            path=inp.get("path"),
            name_hint=inp.get("name_hint", "query_result"),
        )
    except Exception as exc:
        return {"error": f"CSV export failed: {exc}"}
    return {"success": True, "csv_path": path, "row_count": rt.last_result.row_count}


def _tool_export_excel(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    if rt.last_result is None:
        return {"error": "No query result to export. Run execute_sql first."}
    from .exporter import export_excel
    try:
        path = export_excel(
            rt.last_result.columns,
            rt.last_result.rows,
            path=inp.get("path"),
            name_hint=inp.get("name_hint", "query_result"),
        )
    except Exception as exc:
        return {"error": f"Excel export failed: {exc}"}
    return {"success": True, "excel_path": path, "row_count": rt.last_result.row_count}


def _tool_export_pdf(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    if rt.last_result is None:
        return {"error": "No query result to export. Run execute_sql first."}
    from .exporter import export_pdf
    try:
        path = export_pdf(
            rt.last_result.columns,
            rt.last_result.rows,
            path=inp.get("path"),
            name_hint=inp.get("name_hint", "query_result"),
            title=inp.get("title", "Query Result Report"),
        )
    except Exception as exc:
        return {"error": f"PDF export failed: {exc}"}
    return {"success": True, "pdf_path": path, "row_count": rt.last_result.row_count}


_TOOL_HANDLERS = {
    "match_tables": _tool_match_tables,
    "match_metrics": _tool_match_metrics,
    "build_metric_sql": _tool_build_metric_sql,
    "run_attribution": _tool_run_attribution,
    "get_table_schema": _tool_get_table_schema,
    "get_max_partition": _tool_get_max_partition,
    "explain_sql": _tool_explain_sql,
    "execute_sql": _tool_execute_sql,
    "get_result_page": _tool_get_result_page,
    "export_csv": _tool_export_csv,
    "export_excel": _tool_export_excel,
    "export_pdf": _tool_export_pdf,
}


def execute_text2sql_tool(
    name: str, tool_input: dict[str, Any], runtime: Text2SQLRuntime
) -> str:
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
    try:
        result = handler(tool_input, runtime)
    except Exception as exc:
        result = {"error": f"Tool '{name}' failed: {exc}"}
    return json.dumps(result, ensure_ascii=False, default=str)
