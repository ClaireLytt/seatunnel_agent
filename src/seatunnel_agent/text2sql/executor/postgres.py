"""PostgreSQL executor via psycopg2."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .base import DatabaseExecutor, QueryResult

if TYPE_CHECKING:
    from ..schema import TableSchema

_PG_SCHEMA = os.getenv("PG_SCHEMA", "public")

_COLUMNS_SQL = (
    "SELECT c.column_name, c.data_type, "
    "COALESCE(pgd.description, '') AS comment "
    "FROM information_schema.columns c "
    "LEFT JOIN pg_catalog.pg_statio_all_tables st "
    "  ON st.relname = c.table_name AND st.schemaname = c.table_schema "
    "LEFT JOIN pg_catalog.pg_description pgd "
    "  ON pgd.objoid = st.relid "
    "  AND pgd.objsubid = c.ordinal_position "
    "WHERE c.table_schema = %s AND c.table_name = %s "
    "ORDER BY c.ordinal_position"
)

_TABLE_COMMENT_SQL = (
    "SELECT obj_description(oid) FROM pg_class "
    "WHERE relname = %s AND relkind = 'r'"
)

_LIST_TABLES_SQL = (
    "SELECT tablename FROM pg_catalog.pg_tables "
    "WHERE schemaname = %s ORDER BY tablename"
)


class PostgresExecutor(DatabaseExecutor):

    def __init__(self, config) -> None:
        super().__init__(config)
        self.schema = _PG_SCHEMA

    def _connect(self):
        try:
            import psycopg2
        except ImportError as exc:
            raise RuntimeError(
                "psycopg2 is not installed. Install with: "
                "pip install psycopg2-binary"
            ) from exc
        conn = psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            dbname=self.config.database or "postgres",
            user=self.config.username or "postgres",
            password=self.config.password or "",
            connect_timeout=self.config.timeout_s,
        )
        conn.autocommit = True
        return conn

    def run(self, sql: str, max_rows: int = 1000) -> QueryResult:
        return self._run_dbapi(sql, max_rows)

    def _list_tables(self, cursor) -> list[str]:
        cursor.execute(_LIST_TABLES_SQL, (self.schema,))
        return [row[0] for row in cursor.fetchall()]

    def _describe_with(self, cursor, table_name: str) -> TableSchema:
        from ..schema import ColumnSchema, TableSchema

        cursor.execute(_COLUMNS_SQL, (self.schema, table_name))
        columns = [
            ColumnSchema(name=r[0], dtype=r[1], comment=r[2] or "")
            for r in cursor.fetchall()
        ]
        cursor.execute(_TABLE_COMMENT_SQL, (table_name,))
        cr = cursor.fetchone()
        return TableSchema(
            database=self.config.database,
            name=table_name,
            comment=(cr[0] or "") if cr else "",
            columns=columns,
            partition_columns=[],
        )

    def show_tables(self) -> list[str]:
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            return self._list_tables(cursor)
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
            tables = self._list_tables(cursor)
            return [self._describe_with(cursor, t) for t in tables]
        finally:
            if cursor:
                cursor.close()
            conn.close()
