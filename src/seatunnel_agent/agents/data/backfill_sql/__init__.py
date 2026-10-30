"""数据回溯与补数 SQL — 业务日期 × 分区 → 安全幂等的历史补数语句.

Deterministic core: parse a JSON backfill spec (target table, partition
column, business date range, source SELECT with a ``{date}``
placeholder, write mode, dialect) and generate one partition-bounded,
idempotent statement block per business date, plus pre-flight row-count
checks.  Unbounded reads are rejected, the date range is capped, and
the SQL is generated — never executed.
"""

from .bridge import specs_from_plan
from .generator import (
    BackfillSpec,
    BackfillSql,
    DateStatements,
    generate,
    parse_spec,
)
from .report import render_markdown

__all__ = [
    "BackfillSpec",
    "BackfillSql",
    "DateStatements",
    "generate",
    "parse_spec",
    "render_markdown",
    "specs_from_plan",
]
