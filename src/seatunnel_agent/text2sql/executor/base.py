"""Abstract base classes for database executors.

Every supported datasource (Hive, MySQL, SQL Server, Spark SQL, Flink SQL,
ClickHouse, Doris, PostgreSQL) implements ``DatabaseExecutor`` so the agent
layer stays engine-agnostic.
"""

from __future__ import annotations

import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..schema import TableSchema

_TABLE_NAME_RE = re.compile(r"^\w+\.\w+$")

DS_TYPES = ("hive", "mysql", "sqlserver", "sparksql", "flinksql",
            "clickhouse", "doris", "postgresql")

PARTITION_ENGINES = frozenset({"hive", "sparksql"})

DS_DEFAULTS: dict[str, dict[str, object]] = {
    "hive":       {"port": 10000, "database": "default"},
    "mysql":      {"port": 3306,  "database": ""},
    "sqlserver":  {"port": 1433,  "database": "master"},
    "sparksql":   {"port": 10001, "database": "default"},
    "flinksql":   {"port": 0,     "database": "default"},
    "clickhouse": {"port": 8123,  "database": "default"},
    "doris":      {"port": 9030,  "database": ""},
    "postgresql": {"port": 5432,  "database": "postgres"},
}

DIALECT_NAMES: dict[str, str] = {
    "hive":       "Hive SQL",
    "mysql":      "MySQL",
    "sqlserver":  "SQL Server (T-SQL)",
    "sparksql":   "Spark SQL",
    "flinksql":   "Flink SQL",
    "clickhouse": "ClickHouse",
    "doris":      "Doris",
    "postgresql": "PostgreSQL",
}

DEFAULT_SCHEMA_DDL_PATH = "config/schema_ddl.sql"


@dataclass
class DatabaseConfig:
    ds_type: str
    host: str
    port: int
    database: str
    username: str | None = None
    password: str | None = None
    timeout_s: int = 300


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    elapsed_ms: int
    row_count: int
    truncated: bool = False


class DatabaseExecutor(ABC):
    """Interface that every concrete executor must implement."""

    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config
        self._partition_cache: dict[str, str] = {}

    @abstractmethod
    def _connect(self):
        ...

    @abstractmethod
    def run(self, sql: str, max_rows: int = 1000) -> QueryResult:
        ...

    @abstractmethod
    def show_tables(self) -> list[str]:
        ...

    @abstractmethod
    def describe_table(self, table_name: str) -> TableSchema:
        ...

    @abstractmethod
    def fetch_all_schemas(self) -> list[TableSchema]:
        ...

    def test_connection(self) -> tuple[bool, str]:
        """Test connectivity — override only if the default doesn't work."""
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

    def get_max_partition(self, full_table_name: str, refresh: bool = False) -> str | None:
        return None

    # ── Shared helpers ──

    def _run_dbapi(self, sql: str, max_rows: int = 1000,
                   strip_table_prefix: bool = False) -> QueryResult:
        """Generic DB-API 2.0 execute-and-fetch."""
        start = time.time()
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            descs = cursor.description or []
            if strip_table_prefix:
                columns = [d[0].split(".")[-1] for d in descs]
            else:
                columns = [d[0] for d in descs]
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


def schema_ddl_path_from_env() -> str:
    return os.getenv("SCHEMA_DDL_PATH", DEFAULT_SCHEMA_DDL_PATH)


_ENV_PREFIX: dict[str, str] = {
    "hive":       "HIVE",
    "mysql":      "MYSQL",
    "sqlserver":  "MSSQL",
    "sparksql":   "SPARK",
    "flinksql":   "FLINK",
    "clickhouse": "CLICKHOUSE",
    "doris":      "DORIS",
    "postgresql": "PG",
}


def config_from_env(ds_type: str) -> DatabaseConfig | None:
    """Build a DatabaseConfig from environment variables for *ds_type*.

    Returns ``None`` when the HOST variable is unset / empty, meaning
    the user hasn't configured this engine in ``.env``.
    """
    prefix = _ENV_PREFIX.get(ds_type)
    if prefix is None:
        return None

    # SparkSQL reuses HIVE_* vars when SPARK_* are absent
    host = os.getenv(f"{prefix}_HOST", "").strip()
    if not host and ds_type == "sparksql":
        host = os.getenv("HIVE_HOST", "").strip()
        prefix = "HIVE"
    if not host:
        return None

    defaults = DS_DEFAULTS.get(ds_type, {})
    default_port = str(defaults.get("port", 10000))
    default_db = str(defaults.get("database", "default"))

    return DatabaseConfig(
        ds_type=ds_type,
        host=host,
        port=int(os.getenv(f"{prefix}_PORT", default_port)),
        database=os.getenv(f"{prefix}_DATABASE", default_db),
        username=os.getenv(f"{prefix}_USERNAME") or None,
        password=os.getenv(f"{prefix}_PASSWORD") or None,
        timeout_s=int(os.getenv(f"{prefix}_TIMEOUT", "300")),
    )


_EXECUTOR_REGISTRY: dict[str, tuple[str, str]] = {
    "hive":       (".hive",       "HiveExecutor"),
    "mysql":      (".mysql",      "MySQLExecutor"),
    "sqlserver":  (".sqlserver",  "SqlServerExecutor"),
    "sparksql":   (".spark",      "SparkSqlExecutor"),
    "flinksql":   (".flink",      "FlinkSqlExecutor"),
    "clickhouse": (".clickhouse", "ClickHouseExecutor"),
    "doris":      (".doris",      "DorisExecutor"),
    "postgresql": (".postgres",   "PostgresExecutor"),
}


def create_executor(config: DatabaseConfig) -> DatabaseExecutor:
    """Factory: lazily import and instantiate the right executor."""
    import importlib

    entry = _EXECUTOR_REGISTRY.get(config.ds_type)
    if entry is None:
        raise ValueError(f"Unknown datasource type: {config.ds_type!r}. Supported: {DS_TYPES}")
    module_name, class_name = entry
    mod = importlib.import_module(module_name, package=__package__)
    cls = getattr(mod, class_name)
    return cls(config)
