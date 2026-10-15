"""ClickHouse executor via clickhouse-connect."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .base import DatabaseExecutor, QueryResult

if TYPE_CHECKING:
    from ..schema import TableSchema


class ClickHouseExecutor(DatabaseExecutor):

    def _connect(self):
        try:
            import clickhouse_connect
        except ImportError as exc:
            raise RuntimeError(
                "clickhouse-connect is not installed. Install with: "
                "pip install clickhouse-connect"
            ) from exc
        return clickhouse_connect.get_client(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database or "default",
            username=self.config.username or "default",
            password=self.config.password or "",
        )

    def run(self, sql: str, max_rows: int = 1000) -> QueryResult:
        start = time.time()
        client = self._connect()
        try:
            result = client.query(sql, settings={"max_result_rows": max_rows + 1})
            columns = list(result.column_names)
            rows = [tuple(r) for r in result.result_rows]
            truncated = len(rows) > max_rows
            if truncated:
                rows = rows[:max_rows]
        finally:
            client.close()
        elapsed_ms = int((time.time() - start) * 1000)
        return QueryResult(
            columns=columns,
            rows=rows,
            elapsed_ms=elapsed_ms,
            row_count=len(rows),
            truncated=truncated,
        )

    def show_tables(self) -> list[str]:
        client = self._connect()
        try:
            result = client.query("SHOW TABLES")
            return [row[0] for row in result.result_rows]
        finally:
            client.close()

    def _describe_with(self, client, table_name: str) -> TableSchema:
        from ..schema import ColumnSchema, TableSchema

        result = client.query(
            "SELECT name, type, comment "
            "FROM system.columns "
            "WHERE database = {db:String} AND table = {tbl:String} "
            "ORDER BY position",
            parameters={"db": self.config.database, "tbl": table_name},
        )
        columns = [
            ColumnSchema(name=r[0], dtype=r[1], comment=r[2] or "")
            for r in result.result_rows
        ]
        comment_result = client.query(
            "SELECT comment FROM system.tables "
            "WHERE database = {db:String} AND name = {tbl:String}",
            parameters={"db": self.config.database, "tbl": table_name},
        )
        comment = ""
        if comment_result.result_rows:
            comment = comment_result.result_rows[0][0] or ""
        return TableSchema(
            database=self.config.database,
            name=table_name,
            comment=comment,
            columns=columns,
            partition_columns=[],
        )

    def describe_table(self, table_name: str) -> TableSchema:
        client = self._connect()
        try:
            return self._describe_with(client, table_name)
        finally:
            client.close()

    def fetch_all_schemas(self) -> list[TableSchema]:
        client = self._connect()
        try:
            result = client.query("SHOW TABLES")
            tables = [row[0] for row in result.result_rows]
            return [self._describe_with(client, tbl) for tbl in tables]
        finally:
            client.close()

    def test_connection(self) -> tuple[bool, str]:
        try:
            client = self._connect()
            try:
                client.query("SELECT 1")
            finally:
                client.close()
            return True, f"{self.config.host}:{self.config.port}/{self.config.database}"
        except Exception as exc:
            return False, str(exc)
