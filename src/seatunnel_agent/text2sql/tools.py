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
from .metrics import (
    MetricError,
    MetricStore,
    build_metric_sql,
    build_metric_series_sql,
    parse_date,
    parse_time_range,
)
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
            "and which keywords matched. May also return value_hits — actual "
            "cell values from a value index that appear in the question "
            "(e.g. a region name): quote them VERBATIM in WHERE conditions. "
            "Call this first unless the user already named an exact table."
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
            "Dimensions must come from the metric's allowed list, verbatim — "
            "including dim-table dimensions spelled 'alias.column' on star "
            "metrics (metrics with joins). For star metrics, qualify "
            "extra_filters columns yourself (fact columns are auto-prefixed "
            "with 't.'; dim columns need their join alias). For partitioned "
            "time columns provide a date range or max_partition (from "
            "get_max_partition)."
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
            "attributions automatically, plus an exact two-factor split "
            "(numerator_effect + denominator_effect = ratio delta). Set "
            "cross=true (or cross_dimensions=[d1,d2]) for a crossed "
            "two-dimension drill-down when one dimension alone doesn't "
            "explain the move. Costs 2 + 2×dimensions SQL queries (+2 with "
            "cross) — call it ONCE per question. The result table is shown "
            "to the user automatically (waterfall chart included)."
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
                    "description": (
                        "Comparison period start (omit when compare_mode is set)"
                    ),
                },
                "prev_end": {
                    "type": "string",
                    "description": "Comparison period end (inclusive; defaults to prev_start)",
                },
                "compare_mode": {
                    "type": "string",
                    "enum": ["mom", "wow", "yoy"],
                    "description": (
                        "Derive the comparison period deterministically from "
                        "the current one: mom=环比 preceding period of equal "
                        "length, wow=周同比 minus 7 days, yoy=同比 same dates "
                        "last year. PREFER this over computing prev dates "
                        "yourself."
                    ),
                },
                "export_report": {
                    "type": "boolean",
                    "description": (
                        "Also export a standalone Markdown analysis report "
                        "(set true when the user asks for a 报告/导出)"
                    ),
                },
                "dimension": {
                    "type": "string",
                    "description": "Drill down on this single dimension only (optional)",
                },
                "cross": {
                    "type": "boolean",
                    "description": (
                        "Also drill the crossed combination of the two most "
                        "explanatory dimensions (+2 SQLs)"
                    ),
                },
                "cross_dimensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Explicit pair of dimensions to cross-drill, e.g. "
                        "[\"channel\", \"province\"] (overrides cross)"
                    ),
                },
                "extra_filters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional SQL boolean conditions applied to both periods",
                },
            },
            "required": ["metric", "curr_start"],
        },
    },
    {
        "name": "trace_metric",
        "description": (
            "Trace a defined metric's data provenance (指标溯源: 这个数从哪些"
            "表怎么算出来的): returns the caliber level (source table, "
            "expression, constant filters) plus the upstream table chain from "
            "the data-lineage graph when T2S_LINEAGE_SQL_DIR is configured. "
            "Use for '这个指标的数据来源/加工链路' questions — do NOT execute "
            "SQL for those. Ratio metrics trace both numerator and denominator."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "description": "Metric name as returned by match_metrics",
                },
                "depth": {
                    "type": "integer",
                    "description": "Upstream traversal depth (default 3)",
                },
            },
            "required": ["metric"],
        },
    },
    {
        "name": "execute_sql",
        "description": (
            "Validate and execute a SELECT statement on the connected database. "
            "Rejects non-SELECT statements and non-whitelisted tables; enforces "
            "a row LIMIT. Returns columns, preview rows, row count and elapsed "
            "time. A CSV download link is shown automatically. The result may "
            "carry advisory fields: review_findings (static SQL-review issues "
            "found before execution) and skew_hints (data-skew patterns, "
            "attached when the query ran slow) — mention the critical ones to "
            "the user, clearly marked as 静态检查提示."
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
        "name": "review_sql",
        "description": (
            "Static SQL code review (no execution): deterministic linter over "
            "GROUP BY completeness, cartesian joins, = NULL, partition "
            "filters, division-by-zero and more. Use when the user asks to "
            "审查/检查 a SQL statement or pastes SQL asking 有没有问题. "
            "This makes Chat BI the single conversational entry — no need to "
            "send the user to the /sqlreview page for a quick check."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "The SQL to review"},
                "dialect": {
                    "type": "string",
                    "description": (
                        "hive/spark/flink/maxcompute/mysql/postgresql/"
                        "sqlserver/clickhouse/doris/sqlite (default: the "
                        "session's data source)"
                    ),
                },
            },
            "required": ["sql"],
        },
    },
    {
        "name": "skew_check",
        "description": (
            "Static data-skew analysis for batch SQL (spark/hive/maxcompute): "
            "COUNT(DISTINCT) single-point, NULL join keys, global sort, "
            "join-key functions and more, with engine-parameter suggestions. "
            "Use when the user pastes a batch SQL asking 会不会倾斜/为什么慢 "
            "(for an already-executed slow query the result carries "
            "skew_hints automatically)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "The SQL to analyze"},
                "dialect": {
                    "type": "string",
                    "description": "spark / hive / maxcompute (default spark)",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "name": "transpile_sql",
        "description": (
            "Deterministic SQL dialect translation (sqlglot) with a "
            "structured incompatibility report. Use when the user asks to "
            "转成/翻译成 another dialect (e.g. hive SQL 转 doris)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "The SQL to translate"},
                "target_dialect": {
                    "type": "string",
                    "description": "hive / spark / doris / starrocks",
                },
                "source_dialect": {
                    "type": "string",
                    "description": "Source dialect (omit to auto-infer)",
                },
            },
            "required": ["sql", "target_dialect"],
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
        "name": "forecast_metric",
        "description": (
            "Forecast a defined metric's next N days (预测/未来趋势: 预测下周"
            "GMV / 未来7天订单量会怎样). Builds the metric's caliber-consistent "
            "daily series via the semantic layer, then fits a deterministic "
            "LLM-free model (OLS linear trend + weekday seasonality once the "
            "history covers two full weeks) and returns per-day point "
            "forecasts with a 95% interval. Works for ratio metrics too. "
            "Costs 1 SQL query. Present the numbers as a model estimate, "
            "never as a guarantee; mention the interval width when σ is "
            "large relative to the forecast."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "description": "Metric name as returned by match_metrics",
                },
                "horizon_days": {
                    "type": "integer",
                    "description": "Days to forecast ahead (default 7, max 30)",
                },
                "history_days": {
                    "type": "integer",
                    "description": (
                        "History window length used to fit the model "
                        "(default 28, min 14, max 180)"
                    ),
                },
                "end_date": {
                    "type": "string",
                    "description": (
                        "Last history day, YYYY-MM-DD or yyyyMMdd "
                        "(default: yesterday)"
                    ),
                },
                "user_query": {
                    "type": "string",
                    "description": "The user's original question (for the audit log)",
                },
            },
            "required": ["metric"],
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
    _lineage_graph: Any = field(default=None, repr=False)
    _lineage_dir: str = field(default="", repr=False)
    _value_index: Any = field(default=None, repr=False)
    _value_index_store: Any = field(default=None, repr=False)

    @property
    def value_index(self):
        """Value-level index (cell values -> table/column), lazily loaded or
        auto-built where cheap; None when unavailable. A None result is
        cached too (no per-call schema hashing on large stores); the store
        swap on connect/table-filtering triggers the retry."""
        if self._value_index_store is not self.store:
            from .values import load_or_build
            self._value_index = load_or_build(self)
            self._value_index_store = self.store
        return self._value_index

    @property
    def retriever(self):
        """Hybrid retriever, rebuilt whenever the schema store or metric
        store is swapped (table-whitelist filtering replaces the store)."""
        from .retrieval import HybridRetriever
        if (self._retriever is None
                or self._retriever.store is not self.store
                or self._retriever.metric_store is not self.metrics):
            self._retriever = HybridRetriever(self.store, metric_store=self.metrics)
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
    out: dict[str, Any] = {
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

    # Value-level hits: actual cell values appearing in the question.
    try:
        index = rt.value_index
        hits = index.search(query) if index is not None else []
    except Exception:
        hits = []  # strictly additive — never break table matching
    if hits:
        out["value_hits"] = [
            {"table": h.table, "column": h.column, "value": h.value}
            for h in hits
        ]
        out["value_hits_note"] = (
            "These are ACTUAL cell values matching the question. Use them "
            "verbatim in WHERE conditions (e.g. column = 'value') instead of "
            "guessing literals."
        )
        # A value hit can surface a table the name/comment channels missed.
        seen = {c["table"] for c in out["candidates"]}
        for h in hits:
            if h.table not in seen:
                table = rt.store.get(h.table)
                if table is None:
                    continue
                seen.add(h.table)
                out["candidates"].append({
                    "table": table.full_name,
                    "comment": table.comment,
                    "score": 0.0,
                    "table_type": table.table_type,
                    "name_hits": [],
                    "comment_hits": [],
                    "matched_columns": [h.column],
                    "value_match": True,
                })
        out["count"] = len(out["candidates"])
    return out


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
        if m.joins:
            payload["joins"] = [
                {"table": j.table, "alias": j.alias, "type": j.join_type,
                 "on": f"t.{j.local_key} = {j.alias}.{j.remote_key}"}
                for j in m.joins
            ]
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
    try:
        matches = rt.retriever.rank_metrics(query, top_n=5)
    except Exception:  # retrieval must never break the tool — degrade
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


def _tool_forecast_metric(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    from datetime import date, timedelta

    from .forecast import forecast_series
    from .partition import TimeRange

    if rt.metrics is None or len(rt.metrics) == 0:
        return {"error": "No metric definitions loaded (metrics.yaml)"}
    name = str(inp.get("metric", "")).strip()
    metric = rt.metrics.get(name)
    if metric is None:
        known = ", ".join(m.name for m in rt.metrics.metrics)
        return {"error": f"Metric '{name}' is not defined. Known metrics: {known}"}

    try:
        horizon = max(1, min(int(inp.get("horizon_days") or 7), 30))
        history = max(14, min(int(inp.get("history_days") or 28), 180))
    except (TypeError, ValueError):
        return {"error": "horizon_days / history_days must be integers"}

    try:
        end_raw = str(inp.get("end_date", "") or "").strip()
        end = parse_date(end_raw) if end_raw else date.today() - timedelta(days=1)
        start = end - timedelta(days=history - 1)
        sql = build_metric_series_sql(
            metric, rt.metrics, rt.store, TimeRange(start=start, end=end),
        )
    except MetricError as exc:
        return {"error": str(exc)}

    validation = validate_sql(sql, rt.store)
    if not validation.ok:
        return {"error": "SQL rejected: " + "; ".join(validation.errors), "sql": sql}
    final_sql = enforce_limit(sql, default_limit=rt.default_limit, dialect=rt.ds_type)
    try:
        result = rt.executor.run(final_sql, max_rows=rt.default_limit)
    except Exception as exc:
        return {"error": _sanitize_db_error(str(exc)), "sql": sql}
    if result.truncated or result.row_count >= rt.default_limit:
        # the ascending ORDER BY + LIMIT would silently keep the OLDEST
        # rows and forecast from stale history — refuse instead
        return {
            "error": (
                f"日序列达到 {rt.default_limit} 行上限，最近的历史会被截断。"
                "请减小 history_days，或确认 time_column 是日粒度。"
            ),
            "sql": sql,
        }

    def _day(raw: Any) -> Any:
        s = str(raw).strip()
        try:
            return parse_date(s)
        except MetricError:
            return parse_date(s[:10])  # 'YYYY-MM-DD HH:MM:SS' timestamps

    try:
        # aggregate to day grain: a sub-day time_column yields several rows
        # per day — partial sums of an additive metric are summed; partial
        # ratios cannot be recombined, so refuse
        daily: dict[Any, float | None] = {}
        for r in result.rows:
            if r[0] is None:
                continue
            d = _day(r[0])
            v = None if r[-1] is None else float(r[-1])
            if d in daily:
                if metric.is_ratio:
                    return {
                        "error": (
                            "time_column 粒度细于天，比率指标无法按日重新聚合，"
                            "请为比率的分子/分母使用日粒度时间列"
                        ),
                        "sql": sql,
                    }
                if v is not None:
                    daily[d] = (daily[d] or 0.0) + v
            else:
                daily[d] = v
        points = sorted(daily.items())
    except (MetricError, TypeError, ValueError) as exc:
        return {"error": f"cannot parse the daily series: {exc}", "sql": sql}

    try:
        fc = forecast_series(
            points, horizon=horizon,
            fill="ffill" if metric.is_ratio else "zero",
        )
    except ValueError as exc:
        return {
            "error": f"历史数据不足，无法预测: {exc}",
            "hint": "增大 history_days 或确认该时间范围内有数据",
            "sql": sql,
        }

    rt.logger.log(
        user_query=str(inp.get("user_query", "")),
        generated_sql=final_sql, status="success",
        matched_tables=validation.tables,
        exec_time_ms=result.elapsed_ms, row_count=result.row_count,
        extra={"source": rt.source, "metric": name, "kind": "forecast"},
    )
    return {
        "success": True,
        "metric": name,
        "display_name": metric.display_name,
        "unit": metric.unit,
        "sql": sql,
        "history_tail": [
            {"day": d.isoformat(), "value": v} for d, v in points[-14:]
        ],
        **fc,
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


def _derive_prev_range(curr: Any, mode: str) -> Any:
    """Deterministic comparison-period derivation (mom/wow/yoy)."""
    from datetime import date, timedelta

    from .partition import TimeRange

    start, end = curr.start, curr.end

    def _year_back(d: "date") -> "date":
        try:
            return d.replace(year=d.year - 1)
        except ValueError:  # Feb 29
            return d - timedelta(days=365)

    if mode == "mom":
        span = (end - start).days + 1
        return TimeRange(start=start - timedelta(days=span),
                         end=end - timedelta(days=span))
    if mode == "wow":
        return TimeRange(start=start - timedelta(days=7),
                         end=end - timedelta(days=7))
    if mode == "yoy":
        return TimeRange(start=_year_back(start), end=_year_back(end))
    raise MetricError(f"compare_mode 只支持 mom/wow/yoy (got '{mode}')")


def _run_one_attribution(
    inp: dict[str, Any], rt: Text2SQLRuntime, metric: Any,
) -> "Any":
    from .attribution import run_attribution
    from .metrics import parse_time_range

    curr_range = parse_time_range(
        str(inp.get("curr_start", "") or ""), str(inp.get("curr_end", "") or ""),
    )
    if curr_range is None:
        raise MetricError("归因分析必须提供 curr_start")
    mode = str(inp.get("compare_mode", "") or "").strip().lower()
    if mode:
        prev_range = _derive_prev_range(curr_range, mode)
    else:
        prev_range = parse_time_range(
            str(inp.get("prev_start", "") or ""), str(inp.get("prev_end", "") or ""),
        )
    if prev_range is None:
        raise MetricError("归因分析必须提供 prev_start 或 compare_mode")
    dim = str(inp.get("dimension", "") or "").strip()
    return run_attribution(
        metric, rt.metrics, rt.store,
        _attribution_execute(rt, inp.get("user_query", ""), metric.name),
        curr_range=curr_range,
        prev_range=prev_range,
        dimensions=[dim] if dim else None,
        extra_filters=inp.get("extra_filters") or [],
        cross=bool(inp.get("cross")),
        cross_dimensions=inp.get("cross_dimensions") or None,
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


def _maybe_export_report(
    inp: dict[str, Any], metric: Any, results: list, out: dict[str, Any],
    factor_split: dict[str, Any] | None = None,
) -> None:
    """Export the standalone Markdown analysis report on request."""
    if not inp.get("export_report"):
        return
    try:
        from .attribution import render_attribution_markdown
        from .exporter import _resolve_target

        text = render_attribution_markdown(
            results, title=f"{metric.display_name} 异动归因报告",
            factor_split=factor_split,
        )
        target = _resolve_target(None, f"attribution_{metric.name}", "md")
        target.write_text(text, encoding="utf-8")
        out["report_path"] = str(target.resolve())
    except Exception as exc:  # report is a bonus — never fail the analysis
        out["report_error"] = str(exc)


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

            from .attribution import ratio_factor_split

            prev_ratio = _ratio(num_res.prev_total, den_res.prev_total)
            curr_ratio = _ratio(num_res.curr_total, den_res.curr_total)
            split = ratio_factor_split(
                num_res.prev_total, num_res.curr_total,
                den_res.prev_total, den_res.curr_total,
            )
            out: dict[str, Any] = {
                "success": True,
                "metric": metric.name,
                "type": "ratio",
                "prev_ratio": round(prev_ratio, 6) if prev_ratio is not None else None,
                "curr_ratio": round(curr_ratio, 6) if curr_ratio is not None else None,
                "numerator": attribution_to_dict(num_res),
                "denominator": attribution_to_dict(den_res),
            }
            if split is not None:
                out["factor_split"] = {
                    k: round(v, 6) if isinstance(v, float) else v
                    for k, v in split.items()
                }
                out["note"] = (
                    "factor_split is the EXACT decomposition of the ratio's "
                    "move: numerator_effect + denominator_effect = delta "
                    "(numerator_effect = ΔN/D_curr, denominator_effect = "
                    "N_prev/D_curr - N_prev/D_prev). Lead with it, then the "
                    "per-side breakdowns."
                )
            else:
                out["note"] = (
                    "Two-factor split undefined (a period's denominator is 0); "
                    "present the numerator/denominator movements side by side."
                )
            _maybe_export_report(inp, metric, [num_res, den_res], out,
                                 factor_split=split)
            return out

        result = _run_one_attribution(inp, rt, metric)
        _publish_breakdown(rt, result)
        out = {"success": True, "type": "additive", **attribution_to_dict(result)}
        _maybe_export_report(inp, metric, [result], out)
        return out
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
    from .masking import apply_masking

    preview, masked_cols = apply_masking(
        result.columns, result.rows[:_PREVIEW_ROWS],
    )
    out: dict[str, Any] = {
        "success": True,
        "sql": sql,
        "columns": result.columns,
        "preview_rows": [list(r) for r in preview],
        "row_count": result.row_count,
        "truncated": result.truncated,
        "elapsed_ms": result.elapsed_ms,
        **extra,
    }
    if masked_cols:
        out["masked_columns"] = masked_cols
    if validation.column_warnings:
        out["column_warnings"] = validation.column_warnings
    report = check_quality(result.columns, result.rows)
    if report.has_warnings:
        out["quality_warnings"] = [
            {"column": w.column, "warning_type": w.warning_type, "detail": w.detail}
            for w in report.warnings
        ]
    return out


# ds_type -> sql_review linter dialect (module integration: free safety net)
_REVIEW_DIALECT_BY_DS = {
    "hive": "hive", "sparksql": "spark", "flinksql": "flink",
    "mysql": "mysql", "postgresql": "postgresql", "sqlserver": "sqlserver",
    "clickhouse": "clickhouse", "doris": "doris", "sqlite": "sqlite",
}

# ds_type -> data_skew detector dialect (batch warehouses only)
_SKEW_DIALECT_BY_DS = {"hive": "hive", "sparksql": "spark"}

_SLOW_QUERY_MS_DEFAULT = 5000


def _review_findings(sql: str, rt: Text2SQLRuntime) -> list[dict[str, Any]]:
    """Static SQL-review pre-flight (critical/risk only, capped, never raises)."""
    dialect = _REVIEW_DIALECT_BY_DS.get(rt.ds_type)
    if dialect is None:
        return []
    try:
        from ..sql_review.linter import lint_sql
        from ..sql_review.report import Severity

        findings = lint_sql(sql, dialect=dialect, store=rt.store)
        picked = [
            f for f in findings
            if f.severity in (Severity.CRITICAL, Severity.RISK)
        ][:5]
        return [
            {
                "severity": f.severity.value,
                "category": f.category,
                "location": f.location,
                "description": f.description,
                "suggestion": f.suggestion,
            }
            for f in picked
        ]
    except Exception:
        return []  # advisory only — never block execution


def _skew_hints(sql: str, rt: Text2SQLRuntime, elapsed_ms: int) -> list[dict[str, Any]]:
    """Data-skew advice for slow batch-engine queries (never raises)."""
    dialect = _SKEW_DIALECT_BY_DS.get(rt.ds_type)
    if dialect is None:
        return []
    try:
        import os

        threshold = int(os.getenv("T2S_SLOW_QUERY_MS", _SLOW_QUERY_MS_DEFAULT))
    except ValueError:
        threshold = _SLOW_QUERY_MS_DEFAULT
    if elapsed_ms < threshold:
        return []
    try:
        from ..data_skew.detector import detect_skew

        findings, _hints = detect_skew(sql, dialect=dialect)
        return [
            {
                "severity": f.severity.value,
                "category": f.category,
                "description": f.description,
                "suggestion": f.suggestion,
            }
            for f in findings[:3]
        ]
    except Exception:
        return []


def _tool_review_sql(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    """Unified-entry wrapper over the sql_review static linter."""
    sql = str(inp.get("sql", "")).strip()
    if not sql:
        return {"error": "No SQL provided"}
    dialect = str(inp.get("dialect", "") or "").strip().lower() \
        or _REVIEW_DIALECT_BY_DS.get(rt.ds_type, "hive")
    try:
        from ..sql_review.linter import is_known_dialect, lint_sql

        if not is_known_dialect(dialect):
            return {"error": f"Unknown review dialect '{dialect}'"}
        findings = lint_sql(sql, dialect=dialect, store=rt.store)
    except Exception as exc:
        return {"error": f"Review failed: {exc}"}
    by_sev: dict[str, int] = {}
    for f in findings:
        by_sev[f.severity.value] = by_sev.get(f.severity.value, 0) + 1
    return {
        "success": True,
        "dialect": dialect,
        "counts": by_sev,
        "findings": [
            {
                "severity": f.severity.value,
                "category": f.category,
                "location": f.location,
                "description": f.description,
                "impact": f.impact,
                "suggestion": f.suggestion,
            }
            for f in findings[:20]
        ],
        "truncated": len(findings) > 20,
    }


def _tool_skew_check(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    """Unified-entry wrapper over the data_skew static analyzer."""
    sql = str(inp.get("sql", "")).strip()
    if not sql:
        return {"error": "No SQL provided"}
    dialect = str(inp.get("dialect", "") or "").strip().lower() \
        or _SKEW_DIALECT_BY_DS.get(rt.ds_type, "spark")
    try:
        from ..data_skew.agent import static_skew_report
        from ..data_skew.report import render_report

        report = static_skew_report(sql, dialect=dialect)
        return {
            "success": True,
            "dialect": report.dialect,
            "finding_count": len(report.findings),
            "report_markdown": render_report(report, "zh"),
        }
    except Exception as exc:
        return {"error": f"Skew analysis failed: {exc}"}


def _tool_transpile_sql(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    """Unified-entry wrapper over the deterministic dialect translator."""
    sql = str(inp.get("sql", "")).strip()
    target = str(inp.get("target_dialect", "")).strip().lower()
    if not sql or not target:
        return {"error": "sql and target_dialect are required"}
    source = str(inp.get("source_dialect", "") or "").strip().lower() or None
    try:
        from ..sql_transpile.i18n import issue_message
        from ..sql_transpile.transpiler import translate

        result = translate(sql, dst=target, src=source)
    except Exception as exc:
        return {"error": f"Translation failed: {exc}"}
    return {
        "success": True,
        "src_dialect": result.src_dialect,
        "dst_dialect": result.dst_dialect,
        "src_inferred": result.src_inferred,
        "counts": result.counts(),
        "statements": [
            {
                "line": s.line,
                "output_sql": s.output_sql,
                "issues": [
                    {
                        "kind": i.kind,
                        "level": i.level,
                        "message": issue_message("zh", i.kind, i.params),
                    }
                    for i in s.issues[:10]
                ],
            }
            for s in result.statements[:20]
        ],
    }


def _tool_trace_metric(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    """Metric provenance: caliber level + lineage upstream chain."""
    import os

    if rt.metrics is None or len(rt.metrics) == 0:
        return {"error": "No metric definitions loaded (metrics.yaml)"}
    name = str(inp.get("metric", "")).strip()
    metric = rt.metrics.get(name)
    if metric is None:
        known = ", ".join(m.name for m in rt.metrics.metrics)
        return {"error": f"Metric '{name}' is not defined. Known metrics: {known}"}
    depth = max(1, min(int(inp.get("depth", 3) or 3), 10))

    # caliber level (always available)
    if metric.is_ratio:
        parts = [rt.metrics.get(metric.numerator), rt.metrics.get(metric.denominator)]
        parts = [p for p in parts if p is not None and not p.is_ratio]
    else:
        parts = [metric]
    out: dict[str, Any] = {
        "success": True,
        "metric": _metric_payload(metric),
        "sources": [
            {"metric": p.name, "table": p.table, "expression": p.expression,
             "default_filters": list(p.default_filters)}
            for p in parts
        ],
    }

    sql_dir = os.getenv("T2S_LINEAGE_SQL_DIR", "").strip()
    if not sql_dir:
        out["note"] = (
            "上游血缘链未启用：设置 T2S_LINEAGE_SQL_DIR 指向数仓 SQL 目录后，"
            "trace_metric 会附带每张来源表的上游加工链路。当前仅返回口径层。"
        )
        return out

    try:
        graph = rt._lineage_graph
        if graph is None or getattr(rt, "_lineage_dir", "") != sql_dir:
            from ..data_lineage.loaders import build_graph

            graph, warnings = build_graph(sql_dir=sql_dir)
            rt._lineage_graph = graph
            rt._lineage_dir = sql_dir
            if warnings:
                out["lineage_warnings"] = warnings[:5]
        chains = []
        for p in parts:
            chain = graph.upstream_of(p.table, depth=depth)
            chains.append({
                "table": p.table,
                "missing_in_graph": chain.missing_root,
                "upstream_count": chain.upstream_count,
                "upstream": sorted(
                    (
                        {"table": t, "depth": -d}
                        for t, d in chain.depth_of.items()
                        if t != chain.root and d < 0
                    ),
                    key=lambda x: (x["depth"], x["table"]),
                ),
                "edges": [list(e) for e in chain.edges][:50],
                "truncated": chain.truncated,
            })
        out["lineage"] = chains
    except Exception as exc:
        out["lineage_error"] = f"血缘图构建失败: {exc}"
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
    # Cross-module advisories (free safety nets — never block, never raise):
    findings = _review_findings(sql, rt)
    if findings:
        out["review_findings"] = findings
    hints = _skew_hints(sql, rt, result.elapsed_ms)
    if hints:
        out["skew_hints"] = hints
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
    from .masking import apply_masking
    rows, _masked = apply_masking(rt.last_result.columns, rt.last_result.rows)
    try:
        path = export_csv(
            rt.last_result.columns,
            rows,
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
    from .masking import apply_masking
    rows, _masked = apply_masking(rt.last_result.columns, rt.last_result.rows)
    try:
        path = export_excel(
            rt.last_result.columns,
            rows,
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
    from .masking import apply_masking
    rows, _masked = apply_masking(rt.last_result.columns, rt.last_result.rows)
    try:
        path = export_pdf(
            rt.last_result.columns,
            rows,
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
    "forecast_metric": _tool_forecast_metric,
    "trace_metric": _tool_trace_metric,
    "review_sql": _tool_review_sql,
    "skew_check": _tool_skew_check,
    "transpile_sql": _tool_transpile_sql,
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
