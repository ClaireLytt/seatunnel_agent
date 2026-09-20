"""Tool definitions and execution for the Text2SQL agent.

The runtime object carries shared state (schema store, executor, last
result) across tool calls within one agent session.
"""

from __future__ import annotations

import difflib
import json
import re
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
from .exporter import export_csv, export_excel, export_pdf
from .matcher import match_tables
from .partition import classify_table, has_partition_filter
from .qlog import QueryLogger
from .schema import SchemaStore
from .quality import check_quality
from .validator import ValidationResult, enforce_limit, validate_sql

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
        "name": "execute_sql",
        "description": (
            "Validate and execute a SELECT statement on the connected database. "
            "Rejects non-SELECT statements and non-whitelisted tables; enforces "
            "a row LIMIT. Returns columns, preview rows, row count and elapsed "
            "time. The result is kept for export_csv."
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
    ds_type: str = "hive"
    db_config: DatabaseConfig | None = None
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

    @property
    def executor(self) -> DatabaseExecutor:
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
    if not table.is_partitioned:
        return {"error": f"Table '{name}' is not partitioned"}
    try:
        value = rt.executor.get_max_partition(table.full_name)
    except Exception as exc:
        return {"error": str(exc)}
    return {
        "table": table.full_name,
        "partition_column": table.partition_columns[0].name,
        "max_partition": value,
        "table_type": classify_table(table.name),
    }


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
        )
        return _build_success(cached, final_sql, validation, cached=True, elapsed_ms=0)

    try:
        result = rt.executor.run(final_sql, max_rows=rt.default_limit)
    except Exception as exc:
        err = _log_and_reject(
            rt, user_query, final_sql, validation.tables,
            f"Execution failed: {exc}", status="error",
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
        return {"error": f"EXPLAIN failed: {exc}"}

    plan_lines = []
    for row in result.rows:
        plan_lines.append(" | ".join(str(v) for v in row))
    return {
        "success": True,
        "sql": sql,
        "plan": "\n".join(plan_lines),
        "columns": result.columns,
    }


def _tool_export_csv(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    if rt.last_result is None:
        return {"error": "No query result to export. Run execute_sql first."}
    try:
        path = export_csv(
            columns=rt.last_result.columns,
            rows=rt.last_result.rows,
            path=inp.get("path"),
            name_hint=inp.get("name_hint", "query_result"),
        )
    except Exception as exc:
        return {"error": f"CSV export failed: {exc}"}
    return {
        "success": True,
        "csv_path": path,
        "row_count": rt.last_result.row_count,
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
            "Check dialect-specific syntax: date functions, string quoting, JOIN clauses.",
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


def _tool_export_excel(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    if rt.last_result is None:
        return {"error": "No query result to export. Run execute_sql first."}
    try:
        path = export_excel(
            columns=rt.last_result.columns,
            rows=rt.last_result.rows,
            path=inp.get("path"),
            name_hint=inp.get("name_hint", "query_result"),
        )
    except Exception as exc:
        return {"error": f"Excel export failed: {exc}"}
    return {
        "success": True,
        "excel_path": path,
        "row_count": rt.last_result.row_count,
    }


def _tool_export_pdf(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    if rt.last_result is None:
        return {"error": "No query result to export. Run execute_sql first."}
    try:
        path = export_pdf(
            columns=rt.last_result.columns,
            rows=rt.last_result.rows,
            path=inp.get("path"),
            name_hint=inp.get("name_hint", "query_result"),
            title=inp.get("title", "Query Result Report"),
        )
    except Exception as exc:
        return {"error": f"PDF export failed: {exc}"}
    return {
        "success": True,
        "pdf_path": path,
        "row_count": rt.last_result.row_count,
    }


_TOOL_HANDLERS = {
    "match_tables": _tool_match_tables,
    "get_table_schema": _tool_get_table_schema,
    "get_max_partition": _tool_get_max_partition,
    "explain_sql": _tool_explain_sql,
    "execute_sql": _tool_execute_sql,
    "get_result_page": _tool_get_result_page,
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
