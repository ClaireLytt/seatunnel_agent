"""SQLite executor for local demo / testing — no external DB required."""

from __future__ import annotations

import os
import sqlite3
from typing import TYPE_CHECKING

from .base import DatabaseExecutor, QueryResult

if TYPE_CHECKING:
    from ..schema import TableSchema

_DEFAULT_DB_PATH = os.getenv("SQLITE_DB_PATH", "config/demo.db")


class SQLiteExecutor(DatabaseExecutor):

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

    def _describe_with(self, cursor, table_name: str) -> TableSchema:
        from ..schema import ColumnSchema, TableSchema

        safe = table_name.replace("`", "").replace('"', "")
        cursor.execute(f'PRAGMA table_info("{safe}")')
        columns = [
            ColumnSchema(name=r[1], dtype=r[2] or "TEXT", comment="")
            for r in cursor.fetchall()
        ]
        return TableSchema(
            database=self.config.database,
            name=table_name,
            comment="",
            columns=columns,
            partition_columns=[],
        )

    def describe_table(self, table_name: str) -> TableSchema:
        conn = self._connect()
        cursor = conn.cursor()
        try:
            return self._describe_with(cursor, table_name)
        finally:
            cursor.close()
            conn.close()

    def fetch_all_schemas(self) -> list[TableSchema]:
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [r[0] for r in cursor.fetchall()]
            return [self._describe_with(cursor, t) for t in tables]
        finally:
            cursor.close()
            conn.close()

    def test_connection(self) -> tuple[bool, str]:
        try:
            conn = self._connect()
            conn.execute("SELECT 1")
            conn.close()
            db_path = self.config.database or _DEFAULT_DB_PATH
            return True, f"SQLite: {db_path}"
        except Exception as exc:
            return False, str(exc)
