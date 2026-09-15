"""Flink SQL executor — generate-only mode (no execution)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import DatabaseExecutor, QueryResult

if TYPE_CHECKING:
    from ..schema import TableSchema

_FLINK_MSG = (
    "Flink SQL is in generate-only mode. "
    "Load table schemas via a DDL file, then use the agent to generate SQL statements. "
    "Copy the generated SQL to your Flink SQL client to execute."
)


class FlinkSqlExecutor(DatabaseExecutor):
    """Stub executor: Flink SQL only generates queries, does not execute them."""

    def _connect(self):
        raise RuntimeError(_FLINK_MSG)

    def run(self, sql: str, max_rows: int = 1000) -> QueryResult:
        raise RuntimeError(_FLINK_MSG)

    def show_tables(self) -> list[str]:
        raise RuntimeError(_FLINK_MSG)

    def describe_table(self, table_name: str) -> TableSchema:
        raise RuntimeError(_FLINK_MSG)

    def fetch_all_schemas(self) -> list[TableSchema]:
        raise RuntimeError(_FLINK_MSG)

    def test_connection(self) -> tuple[bool, str]:
        return True, "Flink SQL (generate-only mode)"
