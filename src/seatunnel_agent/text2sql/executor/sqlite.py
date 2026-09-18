"""SQLite executor for local demo / testing — no external DB required."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from .base import DatabaseConfig, DatabaseExecutor, QueryResult

if TYPE_CHECKING:
    from ..schema import TableSchema

_DEFAULT_DB_PATH = "config/demo.db"


class SQLiteExecutor(DatabaseExecutor):

    def get_connection(self):
        return self._connect()

    def _connect(self):
        db_path = self.config.database or _DEFAULT_DB_PATH
        return sqlite3.connect(db_path)

    def run(self, sql: str, max_rows: int = 1000) -> QueryResult:
        return self._run_dbapi(sql, max_rows)

    def show_tables(self) -> list[str]:
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            return [r[0] for r in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

    def describe_table(self, table_name: str) -> TableSchema:
        from ..schema import ColumnSchema, TableSchema

        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(f"PRAGMA table_info(`{table_name}`)")
            columns = [
                ColumnSchema(name=r[1], dtype=r[2] or "TEXT", comment="")
                for r in cursor.fetchall()
            ]
        finally:
            cursor.close()
            conn.close()

        return TableSchema(
            database=self.config.database,
            name=table_name,
            comment="",
            columns=columns,
            partition_columns=[],
        )

    def fetch_all_schemas(self) -> list[TableSchema]:
        tables = self.show_tables()
        return [self.describe_table(t) for t in tables]

    def test_connection(self) -> tuple[bool, str]:
        try:
            conn = self._connect()
            conn.execute("SELECT 1")
            conn.close()
            db_path = self.config.database or _DEFAULT_DB_PATH
            return True, f"SQLite: {db_path}"
        except Exception as exc:
            return False, str(exc)
