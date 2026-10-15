"""Text2SQL (Chat BI) agent package.

Turns natural-language questions into safe, executable SQL across multiple
database engines (Hive, MySQL, SQL Server, Spark SQL, Flink SQL, ClickHouse,
Doris, PostgreSQL):
schema matching -> SQL generation (LLM + rules) -> validation -> execution
-> preview + CSV export.
"""

from .schema import ColumnSchema, TableSchema, SchemaStore, parse_ddl
from .validator import validate_sql, enforce_limit, validate_columns, ValidationResult
from .matcher import match_tables, match_columns
from .partition import classify_table, build_partition_clause

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
