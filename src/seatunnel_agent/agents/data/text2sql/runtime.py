"""Shared runtime state and error helpers for the Text2SQL agent.

The runtime object carries shared state (schema store, executor, last
result) across tool calls within one agent session.
"""

from __future__ import annotations

import difflib
import re
import threading
from dataclasses import dataclass, field
from typing import Any

from .cache import SqlResultCache
from .executor import (
    DatabaseConfig,
    DatabaseExecutor,
    QueryResult,
    create_executor,
)
from .metrics import MetricStore
from .qlog import QueryLogger
from .schema import SchemaStore

_DB_CONN_RE = re.compile(
    r"(?:jdbc:[^\s]+|(?:\d{1,3}\.){3}\d{1,3}:\d+|"
    r"password\s*=\s*\S+|user\s*=\s*\S+|"
    r"host\s*=\s*\S+|port\s*=\s*\d+)",
    re.IGNORECASE,
)


def _sanitize_db_error(msg: str) -> str:
    """Strip connection details (host, port, credentials) from DB errors."""
    return _DB_CONN_RE.sub("[REDACTED]", msg)


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
    #: validated-but-unpersisted metric draft awaiting user confirmation
    pending_metric_draft: dict[str, Any] | None = None
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
