"""ClickHouse executor via clickhouse-connect."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .base import ConnectionPool, DatabaseExecutor, QueryResult

if TYPE_CHECKING:
    from ..schema import TableSchema


class ClickHouseExecutor(DatabaseExecutor):

    def get_connection(self):
        if self._pool is None:
            self._pool = ConnectionPool(
                self._connect,
                ping_fn=lambda c: c.query("SELECT 1"),
            )
        return self._pool.acquire()

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
        client = self.get_connection()
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
        client = self.get_connection()
        try:
            result = client.query("SHOW TABLES")
            return [row[0] for row in result.result_rows]
        finally:
            client.close()

    def describe_table(self, table_name: str) -> TableSchema:
        from ..schema import ColumnSchema, TableSchema

        client = self.get_connection()
        try:
            result = client.query(
                "SELECT name, type, comment "
                "FROM system.columns "
                "WHERE database = {db:String} AND table = {tbl:String} "
                "ORDER BY position",
                parameters={"db": self.config.database, "tbl": table_name},
            )
            columns = []
            for row in result.result_rows:
                columns.append(ColumnSchema(
                    name=row[0], dtype=row[1], comment=row[2] or "",
                ))

            comment_result = client.query(
                "SELECT comment FROM system.tables "
                "WHERE database = {db:String} AND name = {tbl:String}",
                parameters={"db": self.config.database, "tbl": table_name},
            )
            comment = ""
            if comment_result.result_rows:
                comment = comment_result.result_rows[0][0] or ""
        finally:
            client.close()

        return TableSchema(
            database=self.config.database,
            name=table_name,
            comment=comment,
            columns=columns,
            partition_columns=[],
        )

    def fetch_all_schemas(self) -> list[TableSchema]:
        from ..schema import ColumnSchema, TableSchema

        client = self.get_connection()
        try:
            result = client.query("SHOW TABLES")
            tables = [row[0] for row in result.result_rows]

            schemas = []
            for tbl in tables:
                col_result = client.query(
                    "SELECT name, type, comment "
                    "FROM system.columns "
                    "WHERE database = {db:String} AND table = {tbl:String} "
                    "ORDER BY position",
                    parameters={"db": self.config.database, "tbl": tbl},
                )
                columns = [
                    ColumnSchema(name=r[0], dtype=r[1], comment=r[2] or "")
                    for r in col_result.result_rows
                ]
                comment_result = client.query(
                    "SELECT comment FROM system.tables "
                    "WHERE database = {db:String} AND name = {tbl:String}",
                    parameters={"db": self.config.database, "tbl": tbl},
                )
                comment = ""
                if comment_result.result_rows:
                    comment = comment_result.result_rows[0][0] or ""
                schemas.append(TableSchema(
                    database=self.config.database, name=tbl,
                    comment=comment, columns=columns, partition_columns=[],
                ))
            return schemas
        finally:
            client.close()

    def test_connection(self) -> tuple[bool, str]:
        try:
            client = self.get_connection()
            try:
                client.query("SELECT 1")
            finally:
                client.close()
            return True, f"{self.config.host}:{self.config.port}/{self.config.database}"
        except Exception as exc:
            return False, str(exc)
