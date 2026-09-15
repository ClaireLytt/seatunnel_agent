"""PostgreSQL executor via psycopg2."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import DatabaseExecutor, QueryResult

if TYPE_CHECKING:
    from ..schema import TableSchema


class PostgresExecutor(DatabaseExecutor):

    def _connect(self):
        try:
            import psycopg2
        except ImportError as exc:
            raise RuntimeError(
                "psycopg2 is not installed. Install with: "
                "pip install psycopg2-binary"
            ) from exc
        return psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            dbname=self.config.database or "postgres",
            user=self.config.username or "postgres",
            password=self.config.password or "",
            connect_timeout=self.config.timeout_s,
        )

    def run(self, sql: str, max_rows: int = 1000) -> QueryResult:
        return self._run_dbapi(sql, max_rows)

    def show_tables(self) -> list[str]:
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT tablename FROM pg_catalog.pg_tables "
                "WHERE schemaname = 'public' "
                "ORDER BY tablename"
            )
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
                "SELECT c.column_name, c.data_type, "
                "COALESCE(pgd.description, '') AS comment "
                "FROM information_schema.columns c "
                "LEFT JOIN pg_catalog.pg_statio_all_tables st "
                "  ON st.relname = c.table_name AND st.schemaname = c.table_schema "
                "LEFT JOIN pg_catalog.pg_description pgd "
                "  ON pgd.objoid = st.relid "
                "  AND pgd.objsubid = c.ordinal_position "
                "WHERE c.table_schema = 'public' AND c.table_name = %s "
                "ORDER BY c.ordinal_position",
                (table_name,),
            )
            columns = []
            for row in cursor.fetchall():
                columns.append(ColumnSchema(
                    name=row[0], dtype=row[1], comment=row[2] or "",
                ))

            cursor.execute(
                "SELECT obj_description(oid) FROM pg_class "
                "WHERE relname = %s AND relkind = 'r'",
                (table_name,),
            )
            comment_row = cursor.fetchone()
            comment = (comment_row[0] or "") if comment_row else ""
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
            cursor.execute(
                "SELECT tablename FROM pg_catalog.pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename"
            )
            tables = [row[0] for row in cursor.fetchall()]

            schemas = []
            for tbl in tables:
                cursor.execute(
                    "SELECT c.column_name, c.data_type, "
                    "COALESCE(pgd.description, '') AS comment "
                    "FROM information_schema.columns c "
                    "LEFT JOIN pg_catalog.pg_statio_all_tables st "
                    "  ON st.relname = c.table_name AND st.schemaname = c.table_schema "
                    "LEFT JOIN pg_catalog.pg_description pgd "
                    "  ON pgd.objoid = st.relid "
                    "  AND pgd.objsubid = c.ordinal_position "
                    "WHERE c.table_schema = 'public' AND c.table_name = %s "
                    "ORDER BY c.ordinal_position",
                    (tbl,),
                )
                columns = [
                    ColumnSchema(name=r[0], dtype=r[1], comment=r[2] or "")
                    for r in cursor.fetchall()
                ]
                cursor.execute(
                    "SELECT obj_description(oid) FROM pg_class "
                    "WHERE relname = %s AND relkind = 'r'",
                    (tbl,),
                )
                cr = cursor.fetchone()
                schemas.append(TableSchema(
                    database=self.config.database, name=tbl,
                    comment=(cr[0] or "") if cr else "",
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
