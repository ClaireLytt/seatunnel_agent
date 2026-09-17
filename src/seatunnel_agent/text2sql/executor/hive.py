"""HiveServer2 executor via pyhive."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import DatabaseExecutor, QueryResult, _TABLE_NAME_RE

if TYPE_CHECKING:
    from ..schema import TableSchema


class HiveExecutor(DatabaseExecutor):
    """Thin wrapper over pyhive with row caps and partition lookup caching."""

    def _connect(self):
        try:
            from pyhive import hive
        except ImportError as exc:
            raise RuntimeError(
                "pyhive is not installed. Install Hive support with: "
                "pip install 'seatunnel-agent[hive]'"
            ) from exc
        conf = {}
        if self.config.timeout_s:
            conf["hive.server2.idle.session.timeout"] = str(self.config.timeout_s * 1000)
            conf["mapreduce.task.timeout"] = str(self.config.timeout_s * 1000)
        return hive.Connection(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            username=self.config.username,
            configuration=conf or None,
        )

    def run(self, sql: str, max_rows: int = 1000) -> QueryResult:
        return self._run_dbapi(sql, max_rows, strip_table_prefix=True)

    def get_max_partition(self, full_table_name: str, refresh: bool = False) -> str | None:
        key = full_table_name.lower()
        if not refresh and key in self._partition_cache:
            return self._partition_cache[key]

        if not _TABLE_NAME_RE.fullmatch(full_table_name):
            raise ValueError(f"Invalid table name: {full_table_name!r}")
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(f"SHOW PARTITIONS {full_table_name}")
            partitions = [r[0] for r in cursor.fetchall()]
        finally:
            if cursor:
                cursor.close()
            conn.close()

        if not partitions:
            raise RuntimeError(f"Table {full_table_name} has no partitions")

        values = []
        for p in partitions:
            first = p.split("/")[0]
            values.append(first.split("=", 1)[1] if "=" in first else first)
        max_value = max(values)
        self._partition_cache[key] = max_value
        return max_value

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
        conn = self._connect()
        try:
            return self._describe_table_with_cursor(table_name, conn)
        finally:
            conn.close()

    def _describe_table_with_cursor(self, table_name: str, conn) -> TableSchema:
        from ..schema import ColumnSchema, TableSchema

        full = f"{self.config.database}.{table_name}"
        if not _TABLE_NAME_RE.fullmatch(full):
            raise ValueError(f"Invalid table name: {full!r}")

        cursor = None
        columns: list[ColumnSchema] = []
        partition_cols: list[ColumnSchema] = []
        comment = ""
        try:
            cursor = conn.cursor()
            cursor.execute(f"DESCRIBE FORMATTED {full}")
            section = "columns"
            for row in cursor.fetchall():
                col_name = (row[0] or "").strip()
                dtype = (row[1] or "").strip()
                col_comment = (row[2] or "").strip()

                if col_name.startswith("# Partition"):
                    section = "partition"
                    continue
                if col_name.startswith("# Detailed") or col_name.startswith("# col_name"):
                    continue
                if col_name == "" and dtype == "":
                    continue
                if col_name == "Table:" or col_name.startswith("Database:"):
                    continue
                if col_name == "Comment:":
                    comment = dtype
                    continue
                if not col_name or not dtype or col_name.startswith("#"):
                    continue

                col = ColumnSchema(name=col_name, dtype=dtype.lower(), comment=col_comment)
                if section == "partition":
                    partition_cols.append(col)
                else:
                    columns.append(col)
        finally:
            if cursor:
                cursor.close()

        return TableSchema(
            database=self.config.database,
            name=table_name,
            comment=comment,
            columns=columns,
            partition_columns=partition_cols,
        )

    def fetch_all_schemas(self) -> list[TableSchema]:
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            cursor = None
            return [self._describe_table_with_cursor(t, conn) for t in tables]
        finally:
            if cursor:
                cursor.close()
            conn.close()

