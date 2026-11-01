"""数据字典生成 — 目录 ± SQL 负载 → 逐列角色/频次/覆盖率骨架.

Deterministic core: parse the catalog (asset_search parser reused),
infer every column's role from its name shape (key/time/measure/flag/
dimension), mine filter/join/group-by usage counts from an optional SQL
workload, and report per-table comment coverage — the empty comments
are the gap list the optional LLM pass drafts descriptions for.  No
database connection.
"""

from .generator import DictEntry, DictResult, TableDict, generate_dict
from .report import render_markdown

__all__ = [
    "DictEntry",
    "DictResult",
    "TableDict",
    "generate_dict",
    "render_markdown",
]
