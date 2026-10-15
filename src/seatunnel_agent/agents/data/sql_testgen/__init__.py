"""SQL test-data generator.

Give it a query (plus optional CREATE TABLE DDL) and it generates minimal
per-table datasets that actually exercise the query:

- equi-join columns share one value pool, so joins produce rows;
- literal predicates (``dt = '2024-01-01'``, ``status IN (...)``) are
  satisfied by most generated rows, so WHERE clauses match;
- boundary rows (NULL / zero / empty string) are mixed in;
- column types come from the DDL when given, otherwise inferred from
  usage and naming.

Optional validation executes the generated data + query on an in-memory
SQLite database (stdlib — zero extra dependencies). Fully deterministic,
no external database, no LLM.
"""

from .generator import (
    ColumnSpec,
    GenResult,
    TableData,
    generate,
    write_outputs,
)
from .report import render_markdown, result_to_dict
from .validator import ValidationResult, validate_with_sqlite

__all__ = [
    "ColumnSpec",
    "GenResult",
    "TableData",
    "generate",
    "write_outputs",
    "render_markdown",
    "result_to_dict",
    "ValidationResult",
    "validate_with_sqlite",
]
