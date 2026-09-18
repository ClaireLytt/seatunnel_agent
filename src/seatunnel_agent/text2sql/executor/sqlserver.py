"""SQL Server executor via pymssql."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import DatabaseExecutor, QueryResult

if TYPE_CHECKING:
    from ..schema import TableSchema


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

    def show_tables(self) -> list[str]:
        conn = self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def describe_table(self, table_name: str) -> TableSchema:
        from ..schema import ColumnSchema, TableSchema

        conn = self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(
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
                "ORDER BY c.column_id",
                (table_name,),
            )
            columns = []
            for row in cursor.fetchall():
                columns.append(ColumnSchema(
                    name=row[0], dtype=row[1], comment=str(row[2] or ""),
                ))

            cursor.execute(
                "SELECT ISNULL(ep.value, '') "
                "FROM sys.tables t "
                "LEFT JOIN sys.extended_properties ep "
                "    ON ep.major_id = t.object_id "
                "   AND ep.minor_id = 0 "
                "   AND ep.name = 'MS_Description' "
                "WHERE t.name = %s",
                (table_name,),
            )
            comment_row = cursor.fetchone()
            comment = str(comment_row[0]) if comment_row else ""
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

        conn = self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
            )
            tables = [row[0] for row in cursor.fetchall()]

            schemas = []
            for tbl in tables:
                cursor.execute(
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
                    "ORDER BY c.column_id",
                    (tbl,),
                )
                columns = [
                    ColumnSchema(name=r[0], dtype=r[1], comment=str(r[2] or ""))
                    for r in cursor.fetchall()
                ]
                cursor.execute(
                    "SELECT ISNULL(ep.value, '') "
                    "FROM sys.tables t "
                    "LEFT JOIN sys.extended_properties ep "
                    "    ON ep.major_id = t.object_id "
                    "   AND ep.minor_id = 0 "
                    "   AND ep.name = 'MS_Description' "
                    "WHERE t.name = %s",
                    (tbl,),
                )
                cr = cursor.fetchone()
                schemas.append(TableSchema(
                    database=self.config.database, name=tbl,
                    comment=str(cr[0]) if cr else "",
                    columns=columns, partition_columns=[],
                ))
            return schemas
        finally:
            if cursor:
                cursor.close()
            conn.close()

