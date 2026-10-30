"""Build the table-characteristics inventory straight from DDL.

``tables_from_ddl`` parses ``CREATE TABLE`` statements and derives the
schema-visible characteristics: the primary-key column and a
conventionally named update-timestamp column (``updated_at``,
``update_time``, ``modify_time``, ``modified_at``, ``gmt_modified``,
``last_modified``).  Row counts, churn, deletes, CDC availability and
latency are not visible in DDL and keep their defaults — the rules
that need them simply do not fire.
"""

from __future__ import annotations

import re

from .advisor import SourceTable

__all__ = ["looks_like_ddl", "tables_from_ddl"]

_CREATE_RE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w.`\"]+)\s*\((.*?)\)\s*"
    r"(?:engine|partitioned|stored|comment|with|distributed|;|$)",
    re.IGNORECASE | re.DOTALL)
_PK_CONSTRAINT_RE = re.compile(
    r"primary\s+key\s*\(\s*([\w`\"]+)", re.IGNORECASE)
_COLUMN_RE = re.compile(r"^\s*([\w`\"]+)\s+(\w+)", re.MULTILINE)
_UPDATE_TS_NAMES = ("updated_at", "update_time", "modify_time",
                    "modified_at", "modified_time", "gmt_modified",
                    "last_modified")
_TIME_TYPES = ("timestamp", "datetime", "date")


def _unquote(name: str) -> str:
    return name.strip().strip('`"')


def looks_like_ddl(text: str) -> bool:
    return bool(re.match(r"\s*(--[^\n]*\n\s*)*create\s+table\b",
                         text or "", re.IGNORECASE))


def tables_from_ddl(text: str) -> list[SourceTable]:
    """CREATE TABLE statements → SourceTable inventory (schema facts only)."""
    tables: list[SourceTable] = []
    for m in _CREATE_RE.finditer(text or ""):
        name = _unquote(m.group(1))
        body = m.group(2)
        pk_col = ""
        pk_match = _PK_CONSTRAINT_RE.search(body)
        if pk_match:
            pk_col = _unquote(pk_match.group(1))
        else:
            for col_m in _COLUMN_RE.finditer(body):
                line_end = body.find("\n", col_m.start())
                line = body[col_m.start():line_end if line_end > 0 else None]
                if re.search(r"primary\s+key", line, re.IGNORECASE):
                    pk_col = _unquote(col_m.group(1))
                    break
        update_ts_col = ""
        for col_m in _COLUMN_RE.finditer(body):
            col = _unquote(col_m.group(1)).lower()
            ctype = col_m.group(2).lower()
            if col in _UPDATE_TS_NAMES and ctype in _TIME_TYPES:
                update_ts_col = _unquote(col_m.group(1))
                break
        tables.append(SourceTable(
            table=name, has_pk=bool(pk_col), pk_col=pk_col,
            has_update_ts=bool(update_ts_col), update_ts_col=update_ts_col))
    if not tables:
        raise ValueError("no CREATE TABLE statements found in DDL")
    return tables
