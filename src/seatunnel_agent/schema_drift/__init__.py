"""Schema drift / data contract checker.

Compare two schema snapshots (CREATE TABLE scripts — files, directories or
pasted DDL) and report every structural change with a severity level:

- **breaking** — removed tables/columns, incompatible type changes,
  partition layout changes
- **risk**     — widening type changes, possible column renames
- **info**     — added tables/columns, comment changes

Sibling of the Change Impact agent: ``/impact`` covers SQL logic changes,
this covers table structure changes. Fully deterministic — no database,
no LLM, nothing executed.
"""

from .differ import (
    ColumnSchema,
    DriftFinding,
    DriftReport,
    TableSchema,
    classify_type_change,
    diff_paths,
    diff_schemas,
    diff_scripts,
    load_schemas,
    parse_schema_script,
)
from .migrate import (
    MigrationPlan,
    MigrationStatement,
    generate_migration,
    render_migration_sql,
)
from .report import render_markdown, report_to_dict

__all__ = [
    "ColumnSchema",
    "DriftFinding",
    "DriftReport",
    "TableSchema",
    "MigrationPlan",
    "MigrationStatement",
    "classify_type_change",
    "diff_paths",
    "diff_schemas",
    "diff_scripts",
    "load_schemas",
    "parse_schema_script",
    "generate_migration",
    "render_migration_sql",
    "render_markdown",
    "report_to_dict",
]
