"""Table-level lineage extraction for the CR report.

Best-effort, regex based: source tables come from FROM/JOIN references
(excluding CTEs and subquery aliases), target tables from INSERT INTO/
OVERWRITE and CREATE TABLE ... AS.
"""

from __future__ import annotations

import os
import re

from .linter import _cte_names, _extract_table_refs, clean_sql
from .report import TableLineage

_INSERT_TARGET_RE = re.compile(
    r"\binsert\s+(?:overwrite\s+(?:table\s+)?|into\s+(?:table\s+)?)"
    r"([`\"]?\w+[`\"]?(?:\.[`\"]?\w+[`\"]?)?)",
    re.IGNORECASE,
)

_CTAS_TARGET_RE = re.compile(
    r"\bcreate\s+(?:temporary\s+)?(?:external\s+)?table\s+"
    r"(?:if\s+not\s+exists\s+)?"
    r"([`\"]?\w+[`\"]?(?:\.[`\"]?\w+[`\"]?)?)",
    re.IGNORECASE,
)


def _norm(name: str) -> str:
    return name.replace("`", "").replace('"', "").lower()


def _max_column_lineage() -> int:
    try:
        return max(1, int(os.getenv("SQLREVIEW_MAX_COLUMN_LINEAGE", "30")))
    except ValueError:
        return 30


_MAX_COLUMN_LINEAGE = _max_column_lineage()


def _column_lineage(sql: str, store=None) -> list[dict[str, object]]:
    """Best-effort column-level lineage via the text2sql tracer."""
    try:
        from ..text2sql.lineage import trace_lineage
        traced = trace_lineage(sql, store=store)
    except Exception:  # noqa: BLE001 — lineage must never break a review
        return []
    columns: list[dict[str, object]] = []
    for col in traced.output_columns[:_MAX_COLUMN_LINEAGE]:
        if col.source_table and col.source_column:
            source = f"{col.source_table}.{col.source_column}"
        elif col.source_column:
            source = col.source_column
        else:
            source = (col.expression or "")[:60]
        if not source:
            continue
        columns.append({
            "output": col.output_name,
            "source": source,
            "aggregated": bool(col.is_aggregation),
        })
    return columns


def extract_table_lineage(sql: str, store=None) -> TableLineage:
    cleaned = clean_sql(sql)
    ctes = _cte_names(cleaned)

    targets: list[str] = []
    for pattern in (_INSERT_TARGET_RE, _CTAS_TARGET_RE):
        for m in pattern.finditer(cleaned):
            name = _norm(m.group(1))
            if name not in targets:
                targets.append(name)

    sources: list[str] = []
    for _off, name, _alias in _extract_table_refs(cleaned):
        if name in ctes or name in targets or name in sources:
            continue
        sources.append(name)

    return TableLineage(
        sources=sources, targets=targets,
        columns=_column_lineage(sql, store=store),
    )
