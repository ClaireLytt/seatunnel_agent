"""Hive query execution over HiveServer2 (thrift).

Uses ``pyhive`` (optional dependency, install with ``pip install
seatunnel-agent[hive]``). Connections are read-only by convention and every
query passes through the validator before reaching this layer.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

_TABLE_NAME_RE = re.compile(r"^\w+\.\w+$")


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    elapsed_ms: int
    row_count: int
    truncated: bool = False


@dataclass
class HiveConfig:
    host: str
    port: int = 10000
    database: str = "default"
    username: str | None = None
    timeout_s: int = 300


DEFAULT_SCHEMA_DDL_PATH = "config/schema_ddl.sql"


def hive_config_from_env() -> HiveConfig | None:
    """Build a HiveConfig from HIVE_* env vars; None if HIVE_HOST is unset."""
    host = os.getenv("HIVE_HOST", "").strip()
    if not host:
        return None
    return HiveConfig(
        host=host,
        port=int(os.getenv("HIVE_PORT", "10000")),
        database=os.getenv("HIVE_DATABASE", "default"),
        username=os.getenv("HIVE_USERNAME") or None,
        timeout_s=int(os.getenv("HIVE_TIMEOUT", "300")),
    )


def schema_ddl_path_from_env() -> str:
    return os.getenv("SCHEMA_DDL_PATH", DEFAULT_SCHEMA_DDL_PATH)


class HiveExecutor:
    """Thin wrapper over pyhive with row caps and partition lookup caching."""

    def __init__(self, config: HiveConfig) -> None:
        self.config = config
        self._partition_cache: dict[str, str] = {}

    def _connect(self):
        try:
            from pyhive import hive
        except ImportError as exc:
            raise RuntimeError(
                "pyhive is not installed. Install Hive support with: "
                "pip install 'seatunnel-agent[hive]'"
            ) from exc
        conf = {}
        if self.config.timeout_s:
            conf["hive.server2.idle.session.timeout"] = str(self.config.timeout_s * 1000)
            conf["mapreduce.task.timeout"] = str(self.config.timeout_s * 1000)
        return hive.Connection(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            username=self.config.username,
            configuration=conf or None,
        )

    def run(self, sql: str, max_rows: int = 1000) -> QueryResult:
        """Execute a (pre-validated) SELECT and fetch up to ``max_rows`` rows."""
        start = time.time()
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [d[0].split(".")[-1] for d in (cursor.description or [])]
            rows = cursor.fetchmany(max_rows + 1)
            truncated = len(rows) > max_rows
            if truncated:
                rows = rows[:max_rows]
        finally:
            if cursor:
                cursor.close()
            conn.close()
        elapsed_ms = int((time.time() - start) * 1000)
        return QueryResult(
            columns=columns,
            rows=[tuple(r) for r in rows],
            elapsed_ms=elapsed_ms,
            row_count=len(rows),
            truncated=truncated,
        )

    def get_max_partition(self, full_table_name: str, refresh: bool = False) -> str:
        """Return the max partition value of a table (cached).

        Parses ``SHOW PARTITIONS`` output like ``pt=20260313`` and returns
        the lexicographically largest value.
        """
        key = full_table_name.lower()
        if not refresh and key in self._partition_cache:
            return self._partition_cache[key]

        if not _TABLE_NAME_RE.fullmatch(full_table_name):
            raise ValueError(f"Invalid table name: {full_table_name!r}")
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(f"SHOW PARTITIONS {full_table_name}")
            partitions = [r[0] for r in cursor.fetchall()]
        finally:
            if cursor:
                cursor.close()
            conn.close()

        if not partitions:
            raise RuntimeError(f"Table {full_table_name} has no partitions")

        values = []
        for p in partitions:
            # "pt=20260313" or "pt=20260313/hour=01" -> first spec value
            first = p.split("/")[0]
            values.append(first.split("=", 1)[1] if "=" in first else first)
        max_value = max(values)
        self._partition_cache[key] = max_value
        return max_value

    def show_tables(self) -> list[str]:
        """Return all table names in the configured database."""
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            return [row[0] for row in cursor.fetchall()]
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def describe_table(self, table_name: str) -> "TableSchema":
        """Fetch column metadata via DESCRIBE and return a TableSchema."""
        conn = self._connect()
        try:
            return self._describe_table_with_cursor(table_name, conn)
        finally:
            conn.close()

    def _describe_table_with_cursor(self, table_name: str, conn) -> "TableSchema":
        """Parse DESCRIBE FORMATTED output using an existing connection."""
        from .schema import ColumnSchema, TableSchema

        full = f"{self.config.database}.{table_name}"
        if not _TABLE_NAME_RE.fullmatch(full):
            raise ValueError(f"Invalid table name: {full!r}")

        cursor = None
        columns: list[ColumnSchema] = []
        partition_cols: list[ColumnSchema] = []
        comment = ""
        try:
            cursor = conn.cursor()
            cursor.execute(f"DESCRIBE FORMATTED {full}")
            section = "columns"
            for row in cursor.fetchall():
                col_name = (row[0] or "").strip()
                dtype = (row[1] or "").strip()
                col_comment = (row[2] or "").strip()

                if col_name.startswith("# Partition"):
                    section = "partition"
                    continue
                if col_name.startswith("# Detailed") or col_name.startswith("# col_name"):
                    continue
                if col_name == "" and dtype == "":
                    continue

                if col_name == "Table:" or col_name.startswith("Database:"):
                    continue
                if col_name == "Comment:":
                    comment = dtype
                    continue

                if not col_name or not dtype or col_name.startswith("#"):
                    continue

                col = ColumnSchema(name=col_name, dtype=dtype.lower(), comment=col_comment)
                if section == "partition":
                    partition_cols.append(col)
                else:
                    columns.append(col)
        finally:
            if cursor:
                cursor.close()

        return TableSchema(
            database=self.config.database,
            name=table_name,
            comment=comment,
            columns=columns,
            partition_columns=partition_cols,
        )

    def fetch_all_schemas(self) -> list["TableSchema"]:
        """Fetch schema for every table in the database using a single connection."""
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            cursor = None
            return [self._describe_table_with_cursor(t, conn) for t in tables]
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def test_connection(self) -> tuple[bool, str]:
        """Try a trivial query; return (ok, message)."""
        try:
            conn = self._connect()
            cursor = None
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            finally:
                if cursor:
                    cursor.close()
                conn.close()
            return True, f"{self.config.host}:{self.config.port}/{self.config.database}"
        except Exception as exc:
            return False, str(exc)
