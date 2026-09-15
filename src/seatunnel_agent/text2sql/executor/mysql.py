"""MySQL executor via pymysql."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import DatabaseExecutor, QueryResult

if TYPE_CHECKING:
    from ..schema import TableSchema


class MySQLExecutor(DatabaseExecutor):

    def _connect(self):
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError(
                "pymysql is not installed. Install with: pip install pymysql"
            ) from exc
        return pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database or None,
            user=self.config.username or "root",
            password=self.config.password or "",
            connect_timeout=self.config.timeout_s,
            charset="utf8mb4",
        )

    def run(self, sql: str, max_rows: int = 1000) -> QueryResult:
        return self._run_dbapi(sql, max_rows)

    def show_tables(self) -> list[str]:
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

    def describe_table(self, table_name: str) -> TableSchema:
        from ..schema import ColumnSchema, TableSchema

        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                "ORDER BY ORDINAL_POSITION",
                (self.config.database, table_name),
            )
            columns = []
            for row in cursor.fetchall():
                columns.append(ColumnSchema(
                    name=row[0], dtype=row[1], comment=row[2] or "",
                ))

            cursor.execute(
                "SELECT TABLE_COMMENT FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (self.config.database, table_name),
            )
            comment_row = cursor.fetchone()
            comment = comment_row[0] if comment_row else ""
        finally:
            if cursor:
                cursor.close()
            conn.close()

        return TableSchema(
            database=self.config.database,
            name=table_name,
            comment=comment,
            columns=columns,
            partition_columns=[],
        )

    def fetch_all_schemas(self) -> list[TableSchema]:
        from ..schema import ColumnSchema, TableSchema

        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]

            schemas = []
            for tbl in tables:
                cursor.execute(
                    "SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT "
                    "FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                    "ORDER BY ORDINAL_POSITION",
                    (self.config.database, tbl),
                )
                columns = [
                    ColumnSchema(name=r[0], dtype=r[1], comment=r[2] or "")
                    for r in cursor.fetchall()
                ]
                cursor.execute(
                    "SELECT TABLE_COMMENT FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                    (self.config.database, tbl),
                )
                cr = cursor.fetchone()
                schemas.append(TableSchema(
                    database=self.config.database, name=tbl,
                    comment=cr[0] if cr else "",
                    columns=columns, partition_columns=[],
                ))
            return schemas
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def test_connection(self) -> tuple[bool, str]:
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
