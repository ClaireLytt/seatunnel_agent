"""DDL parsing and in-memory schema store.

Parses ``CREATE TABLE`` statements (with column/table COMMENTs and
``PARTITIONED BY`` clauses) into structured dataclasses. The schema file
(``schema_ddl.sql``) is the table whitelist: the agent may only query
tables registered here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_INCREMENTAL_SUFFIXES = ("_di", "_hi", "_ri")
_FULL_SUFFIXES = ("_df", "_hf")


@dataclass(frozen=True)
class ColumnSchema:
    name: str
    dtype: str
    comment: str = ""


@dataclass
class TableSchema:
    database: str
    name: str
    comment: str = ""
    columns: list[ColumnSchema] = field(default_factory=list)
    partition_columns: list[ColumnSchema] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.database}.{self.name}" if self.database else self.name

    @property
    def table_type(self) -> str:
        """'incremental' (_di/_hi/_ri), 'full' (_df/_hf), or 'other'."""
        lower = self.name.lower()
        if lower.endswith(_INCREMENTAL_SUFFIXES):
            return "incremental"
        if lower.endswith(_FULL_SUFFIXES):
            return "full"
        return "other"

    @property
    def is_partitioned(self) -> bool:
        return bool(self.partition_columns)

    def find_column(self, name: str) -> ColumnSchema | None:
        lower = name.lower()
        for col in self.columns + self.partition_columns:
            if col.name.lower() == lower:
                return col
        return None

    def find_column_by_comment(self, text: str) -> ColumnSchema | None:
        """Find the column whose comment best contains ``text``."""
        best: ColumnSchema | None = None
        best_len = 0
        for col in self.columns + self.partition_columns:
            if text and text in col.comment:
                # Prefer the shortest comment containing the text (most specific)
                if best is None or len(col.comment) < best_len:
                    best = col
                    best_len = len(col.comment)
        return best

    def to_ddl_summary(self, max_columns: int = 200) -> str:
        lines = [f"TABLE {self.full_name}  -- {self.comment}"]
        lines.append(f"  type: {self.table_type}")
        for col in self.columns[:max_columns]:
            lines.append(f"  {col.name} {col.dtype}  -- {col.comment}")
        if len(self.columns) > max_columns:
            lines.append(f"  ... ({len(self.columns) - max_columns} more columns)")
        if self.partition_columns:
            parts = ", ".join(
                f"{c.name} {c.dtype} -- {c.comment}" for c in self.partition_columns
            )
            lines.append(f"  PARTITIONED BY: {parts}")
        return "\n".join(lines)


_CREATE_RE = re.compile(
    r"CREATE\s+(?:EXTERNAL\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"[`\"]?(?:(\w+)[`\"]?\.)?[`\"]?(\w+)[`\"]?\s*\(",
    re.IGNORECASE,
)

_PARTITIONED_RE = re.compile(r"PARTITIONED\s+BY\s*\(", re.IGNORECASE)

_TABLE_COMMENT_RE = re.compile(r"^\s*COMMENT\s+'((?:[^'\\]|\\.)*)'", re.IGNORECASE)

_COLUMN_RE = re.compile(
    r"^\s*[`\"]?(\w+)[`\"]?\s+([a-zA-Z_]+(?:\s*<[^>]*>)?(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)"
    r"(?:\s+COMMENT\s+'((?:[^'\\]|\\.)*)')?\s*$",
    re.IGNORECASE,
)


def _find_matching_paren(text: str, open_pos: int) -> int:
    """Return index of the ')' matching the '(' at ``open_pos``.

    Skips parens inside single-quoted strings (handles backslash escapes).
    """
    depth = 0
    i = open_pos
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "'":
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == "'":
                    break
                i += 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("Unbalanced parentheses in DDL")


def _split_columns(block: str) -> list[str]:
    """Split a column-definition block on top-level commas."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    i = 0
    n = len(block)
    while i < n:
        ch = block[i]
        if ch == "'":
            current.append(ch)
            i += 1
            while i < n:
                current.append(block[i])
                if block[i] == "\\" and i + 1 < n:
                    i += 1
                    current.append(block[i])
                elif block[i] == "'":
                    break
                i += 1
        elif ch in "(<":
            depth += 1
            current.append(ch)
        elif ch in ")>":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _unescape_comment(raw: str) -> str:
    return raw.replace("\\;", ";").replace("\\n", " ").replace("\\'", "'").strip()


def _parse_column_defs(block: str) -> list[ColumnSchema]:
    columns: list[ColumnSchema] = []
    for part in _split_columns(block):
        part = " ".join(part.split())
        m = _COLUMN_RE.match(part)
        if not m:
            continue
        name, dtype, comment = m.group(1), m.group(2), m.group(3) or ""
        columns.append(ColumnSchema(name=name, dtype=dtype.strip().lower(),
                                    comment=_unescape_comment(comment)))
    return columns


def parse_ddl(text: str) -> list[TableSchema]:
    """Parse all CREATE TABLE statements found in ``text``."""
    tables: list[TableSchema] = []
    pos = 0
    while True:
        m = _CREATE_RE.search(text, pos)
        if not m:
            break
        database = m.group(1) or ""
        name = m.group(2)
        open_paren = m.end() - 1
        close_paren = _find_matching_paren(text, open_paren)
        col_block = text[open_paren + 1:close_paren]
        columns = _parse_column_defs(col_block)

        rest = text[close_paren + 1:]
        table_comment = ""
        partition_columns: list[ColumnSchema] = []

        # Table comment appears after the column block, before PARTITIONED BY.
        next_create = _CREATE_RE.search(rest)
        stmt_tail = rest[: next_create.start()] if next_create else rest

        cm = _TABLE_COMMENT_RE.search(stmt_tail)
        if cm:
            table_comment = _unescape_comment(cm.group(1))

        pm = _PARTITIONED_RE.search(stmt_tail)
        if pm:
            p_open = close_paren + 1 + pm.end() - 1
            p_close = _find_matching_paren(text, p_open)
            partition_columns = _parse_column_defs(text[p_open + 1:p_close])
            pos = p_close + 1
        else:
            pos = close_paren + 1

        tables.append(TableSchema(
            database=database,
            name=name,
            comment=table_comment,
            columns=columns,
            partition_columns=partition_columns,
        ))
    return tables


class SchemaStore:
    """Registry of all known (whitelisted) tables."""

    def __init__(self, tables: list[TableSchema] | None = None) -> None:
        self._tables: dict[str, TableSchema] = {}
        for t in tables or []:
            self.add(t)

    def add(self, table: TableSchema) -> None:
        self._tables[table.full_name.lower()] = table

    def get(self, full_name: str) -> TableSchema | None:
        result = self._tables.get(full_name.lower())
        if result is None:
            key = full_name.lower()
            for t in self._tables.values():
                if t.name.lower() == key:
                    return t
        return result

    @property
    def tables(self) -> list[TableSchema]:
        return list(self._tables.values())

    @property
    def table_names(self) -> list[str]:
        return [t.full_name for t in self._tables.values()]

    def __len__(self) -> int:
        return len(self._tables)

    @classmethod
    def from_file(cls, path: str | Path) -> "SchemaStore":
        text = Path(path).read_text(encoding="utf-8")
        return cls(parse_ddl(text))

    @classmethod
    def from_db(cls, executor) -> "SchemaStore":
        """Build a store by introspecting all tables via any DatabaseExecutor."""
        return cls(executor.fetch_all_schemas())

    def summary(self) -> str:
        """One line per table: name + comment (for the system prompt)."""
        lines = []
        for t in self._tables.values():
            lines.append(f"- {t.full_name}: {t.comment} ({len(t.columns)} columns, "
                         f"type={t.table_type})")
        return "\n".join(lines)
