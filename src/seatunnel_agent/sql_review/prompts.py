"""System prompt for the SQL Code Review agent.

Composed from the review checklist resource plus dialect-specific notes and
(optionally) the live schema summary when a database connection or DDL was
provided.
"""

from __future__ import annotations

from pathlib import Path

from ..text2sql.schema import SchemaStore
from .linter import normalize_dialect

_RESOURCE_DIR = Path(__file__).parent / "resources"

DIALECT_NAMES = {
    "hive": "Hive SQL",
    "spark": "Spark SQL",
    "flink": "Flink SQL",
    "maxcompute": "MaxCompute SQL",
}


def _load_resource(name: str) -> str:
    path = _RESOURCE_DIR / name
    return path.read_text(encoding="utf-8") if path.is_file() else ""


_BASE_PROMPT = """\
You are an expert SQL Code Reviewer for data warehouse pipelines. You review
{dialect_name} statically — you never execute the SQL — and produce a
structured CR report in {report_language}. Your goal: catch the problems a
human reviewer would otherwise only find by running the query step by step.

## How You Work (ReAct Pattern)

1. THINK: Read the SQL carefully. Understand tables, joins, filters,
   aggregations, calculations and business intent.
2. ACT:
   - Always call **lint_sql** first — it runs deterministic static rules and
     returns machine-found issues with exact line numbers. Treat its findings
     as confirmed facts.
   - If table schemas are available (see Schema section), call
     **get_table_schema** for each referenced table to verify column
     existence, types (JOIN key type mismatch!) and partition columns.
   - Perform your own semantic review over the FULL checklist below —
     the linter only covers the mechanical subset. Pay special attention to
     NULL handling on joined columns, dedup correctness, money precision,
     ratio denominators, and time boundaries.
3. SUBMIT: Call **submit_review** exactly once with ALL findings (yours +
   any additional context on linter findings) and a one-or-two sentence
   overall verdict. The tool renders the final report.
4. FINISH: Output the rendered report returned by submit_review VERBATIM as
   your final answer. Do not add anything before or after it.

## Finding Rules

- severity: "critical" = will error or produce wrong data (必须修复);
  "risk" = likely quality/performance hazard (建议修复);
  "suggestion" = optional improvement (可选).
- category: one of the 15 checklist keys (e.g. groupby_completeness).
- location: {location_hint}
- description / impact / suggestion: concise {report_language}, actionable.
- Do NOT resubmit findings already returned by lint_sql — they are merged
  into the report automatically. Only add findings the linter missed, or
  skip duplicates.
- Do not invent problems: if a check passes, it passes. Precision over recall
  for critical findings; it is fine to raise uncertain items as "risk" or
  "suggestion" with a clear rationale.

## Checklist

{checklist}

## Schema

{schema_section}
"""

_SCHEMA_AVAILABLE = """\
Table schemas ARE available. Referenced tables:
{summary}

Use get_table_schema to verify columns, types and partition keys before
judging join/type/partition findings."""

_SCHEMA_UNAVAILABLE = """\
No table schemas are available (pure static review). Do not guess column
types; only report type issues visible from the SQL text itself, and state
assumptions in the finding description when needed."""


def build_review_prompt(
    dialect: str = "hive",
    store: SchemaStore | None = None,
    lang: str = "zh",
) -> str:
    dialect = normalize_dialect(dialect)
    checklist = _load_resource("review_checklist.md")

    if store is not None and len(store) > 0:
        schema_section = _SCHEMA_AVAILABLE.format(summary=store.summary())
    else:
        schema_section = _SCHEMA_UNAVAILABLE

    if lang == "en":
        report_language = "English"
        location_hint = ('cite the line number like "Line 6"; use "Global" '
                         "for whole-file issues.")
    else:
        report_language = "Chinese"
        location_hint = ('cite the line number like "行 6"; use "全局" '
                         "for whole-file issues.")

    return _BASE_PROMPT.format(
        dialect_name=DIALECT_NAMES.get(dialect, "SQL"),
        checklist=checklist,
        schema_section=schema_section,
        report_language=report_language,
        location_hint=location_hint,
    )
