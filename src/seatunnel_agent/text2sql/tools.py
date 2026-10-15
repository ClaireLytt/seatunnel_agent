"""Tool definitions and dispatch for the Text2SQL agent.

Handlers for metric-family tools live in tools_metric, SQL-execution
handlers in tools_sql, and the shared runtime state in runtime."""

from __future__ import annotations

import json
from typing import Any

from .executor import PARTITION_ENGINES
from .exporter import export_csv
from .matcher import match_tables
from .partition import classify_table
from .runtime import (  # noqa: F401 (re-exported for compatibility)
    Text2SQLRuntime,
    _sanitize_db_error,
    _suggest_column,
    classify_error,
)
from .tools_metric import (  # noqa: F401 (re-exported for compatibility)
    _metric_payload,
    _resolve_metric,
    _tool_build_metric_sql,
    _tool_forecast_metric,
    _tool_match_metrics,
    _tool_run_attribution,
    _tool_trace_metric,
)
from .tools_sql import (  # noqa: F401 (re-exported for compatibility)
    _build_sql_error,
    _build_success,
    _check_partition_filters,
    _log_and_reject,
    _review_findings,
    _skew_hints,
    _tool_execute_sql,
    _tool_explain_sql,
    _tool_review_sql,
    _tool_skew_check,
    _tool_transpile_sql,
)


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
