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

from .executor import (
    PARTITION_ENGINES,
    DatabaseConfig,
    DatabaseExecutor,
    QueryResult,
    create_executor,
)
from .exporter import export_csv
from .matcher import match_tables
from .partition import classify_table, has_partition_filter
from .qlog import QueryLogger
from .schema import SchemaStore
from .validator import enforce_limit, validate_sql

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
        "name": "export_csv",
        "description": (
            "Export the most recent query result to a CSV file. Default "
            "location is the user's Desktop with a timestamped filename; "
            "pass 'path' to override (directory or full file path)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional output directory or .csv file path",
                },
                "name_hint": {
                    "type": "string",
                    "description": "Optional short name used in the filename",
                },
            },
            "required": [],
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
    last_sql: str = ""
    _executor: DatabaseExecutor | None = None

    @property
    def executor(self) -> DatabaseExecutor:
        if self._executor is None:
            if self.db_config is None or not self.db_config.host:
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


def _tool_execute_sql(inp: dict[str, Any], rt: Text2SQLRuntime) -> dict[str, Any]:
    sql = inp.get("sql", "")
    user_query = inp.get("user_query", "")

    validation = validate_sql(sql, rt.store)
    if not validation.ok:
        rt.logger.log(
            user_query=user_query, generated_sql=sql, status="rejected",
            matched_tables=validation.tables, error="; ".join(validation.errors),
        )
        return {"error": "SQL rejected: " + "; ".join(validation.errors)}

    missing_partition = []
    if rt.ds_type in PARTITION_ENGINES:
        for tname in validation.tables:
            table = rt.store.get(tname)
            if table and table.is_partitioned:
                pcol = table.partition_columns[0].name
                if not has_partition_filter(sql, pcol):
                    missing_partition.append(f"{table.full_name} (partition column: {pcol})")
    if missing_partition:
        msg = (
            "Partitioned table(s) missing partition filter: "
            + ", ".join(missing_partition)
            + ". Add a WHERE condition on the partition column "
            "(use get_max_partition if no time range was given)."
        )
        rt.logger.log(
            user_query=user_query, generated_sql=sql, status="rejected",
            matched_tables=validation.tables, error=msg,
        )
        return {"error": msg}

    final_sql = enforce_limit(sql, default_limit=rt.default_limit, dialect=rt.ds_type)

    try:
        result = rt.executor.run(final_sql, max_rows=rt.default_limit)
    except Exception as exc:
        rt.logger.log(
            user_query=user_query, generated_sql=final_sql, status="error",
            matched_tables=validation.tables, error=str(exc),
        )
        err: dict[str, Any] = {"error": f"Execution failed: {exc}", "sql": final_sql}
        suggestion = _suggest_column(str(exc), rt)
        if suggestion:
            err["suggestion"] = suggestion
        return err

    rt.last_result = result
    rt.last_sql = final_sql
    rt.logger.log(
        user_query=user_query, generated_sql=final_sql, status="success",
        matched_tables=validation.tables,
        exec_time_ms=result.elapsed_ms, row_count=result.row_count,
    )
    out: dict[str, Any] = {
        "success": True,
        "sql": final_sql,
        "columns": result.columns,
        "preview_rows": [list(r) for r in result.rows[:_PREVIEW_ROWS]],
        "row_count": result.row_count,
        "truncated": result.truncated,
        "elapsed_ms": result.elapsed_ms,
    }
    if validation.column_warnings:
        out["column_warnings"] = validation.column_warnings
    return out


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


_TOOL_HANDLERS = {
    "match_tables": _tool_match_tables,
    "get_table_schema": _tool_get_table_schema,
    "get_max_partition": _tool_get_max_partition,
    "execute_sql": _tool_execute_sql,
    "export_csv": _tool_export_csv,
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
