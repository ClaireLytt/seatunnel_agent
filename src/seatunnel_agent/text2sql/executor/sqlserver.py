"""SQL Server executor via pymssql."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import DatabaseExecutor, QueryResult

if TYPE_CHECKING:
    from ..schema import TableSchema

_COLUMNS_SQL = (
    "SELECT c.name AS column_name, "
    "       t.name + CASE "
    "           WHEN t.name IN ('varchar','nvarchar','char','nchar') "
    "               THEN '(' + CAST(c.max_length AS VARCHAR) + ')' "
    "           WHEN t.name IN ('decimal','numeric') "
    "               THEN '(' + CAST(c.precision AS VARCHAR) + ',' "
    "                    + CAST(c.scale AS VARCHAR) + ')' "
    "           ELSE '' END AS column_type, "
    "       ISNULL(ep.value, '') AS column_comment "
    "FROM sys.columns c "
    "JOIN sys.types t ON c.user_type_id = t.user_type_id "
    "LEFT JOIN sys.extended_properties ep "
    "    ON ep.major_id = c.object_id "
    "   AND ep.minor_id = c.column_id "
    "   AND ep.name = 'MS_Description' "
    "WHERE c.object_id = OBJECT_ID(%s) "
    "ORDER BY c.column_id"
)

_TABLE_COMMENT_SQL = (
    "SELECT ISNULL(ep.value, '') "
    "FROM sys.tables t "
    "LEFT JOIN sys.extended_properties ep "
    "    ON ep.major_id = t.object_id "
    "   AND ep.minor_id = 0 "
    "   AND ep.name = 'MS_Description' "
    "WHERE t.name = %s"
)

_LIST_TABLES_SQL = (
    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
    "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
)


class SqlServerExecutor(DatabaseExecutor):

    def _connect(self):
        try:
            import pymssql
        except ImportError as exc:
            raise RuntimeError(
                "pymssql is not installed. Install with: pip install pymssql"
            ) from exc
        return pymssql.connect(
            server=self.config.host,
            port=str(self.config.port),
            database=self.config.database or "master",
            user=self.config.username or "sa",
            password=self.config.password or "",
            login_timeout=self.config.timeout_s,
            charset="UTF-8",
        )

    def run(self, sql: str, max_rows: int = 1000) -> QueryResult:
        return self._run_dbapi(sql, max_rows)

    def _describe_with(self, cursor, table_name: str) -> TableSchema:
        from ..schema import ColumnSchema, TableSchema

        cursor.execute(_COLUMNS_SQL, (table_name,))
        columns = [
            ColumnSchema(name=r[0], dtype=r[1], comment=str(r[2] or ""))
            for r in cursor.fetchall()
        ]
        cursor.execute(_TABLE_COMMENT_SQL, (table_name,))
        cr = cursor.fetchone()
        return TableSchema(
            database=self.config.database,
            name=table_name,
            comment=str(cr[0]) if cr else "",
            columns=columns,
            partition_columns=[],
        )

    def show_tables(self) -> list[str]:
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(_LIST_TABLES_SQL)
            return [row[0] for row in cursor.fetchall()]
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def describe_table(self, table_name: str) -> TableSchema:
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            return self._describe_with(cursor, table_name)
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def fetch_all_schemas(self) -> list[TableSchema]:
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(_LIST_TABLES_SQL)
            tables = [row[0] for row in cursor.fetchall()]
            return [self._describe_with(cursor, tbl) for tbl in tables]
        finally:
            if cursor:
                cursor.close()
            conn.close()

