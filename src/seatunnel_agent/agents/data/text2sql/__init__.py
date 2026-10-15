"""Text2SQL (Chat BI) agent package.

Turns natural-language questions into safe, executable SQL across multiple
database engines (Hive, MySQL, SQL Server, Spark SQL, Flink SQL, ClickHouse,
Doris, PostgreSQL):
schema matching -> SQL generation (LLM + rules) -> validation -> execution
-> preview + CSV export.
"""

from .matcher import match_columns, match_tables
from .partition import build_partition_clause, classify_table
from .schema import ColumnSchema, SchemaStore, TableSchema, parse_ddl
from .validator import ValidationResult, enforce_limit, validate_columns, validate_sql

__all__ = [
    "ColumnSchema",
    "TableSchema",
    "SchemaStore",
    "parse_ddl",
    "validate_sql",
    "enforce_limit",
    "validate_columns",
    "ValidationResult",
    "match_tables",
    "match_columns",
    "classify_table",
    "build_partition_clause",
]
