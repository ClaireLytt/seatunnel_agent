"""SQL dialect translation agent (hive/spark/doris/starrocks).

Deterministic sqlglot-based translation with a structured incompatibility
report; optional LLM advice on top (never overwrites the deterministic
output). No database connection, no SQL execution.
"""

from .i18n import normalize_lang, tp
from .report import (
    batch_to_dict,
    render_batch_markdown,
    render_markdown,
    result_to_dict,
)
from .transpiler import (
    DIALECTS,
    BatchResult,
    Issue,
    StatementResult,
    TranspileResult,
    collect_sql_files,
    infer_dialect,
    normalize_dialect,
    translate,
    transpile_dir,
)

__all__ = [
    "DIALECTS",
    "BatchResult",
    "Issue",
    "StatementResult",
    "TranspileResult",
    "batch_to_dict",
    "collect_sql_files",
    "infer_dialect",
    "normalize_dialect",
    "normalize_lang",
    "render_batch_markdown",
    "render_markdown",
    "result_to_dict",
    "tp",
    "translate",
    "transpile_dir",
]
