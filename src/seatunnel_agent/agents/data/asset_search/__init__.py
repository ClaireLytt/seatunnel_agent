"""数据资产搜索 — 自然语言需求 × 资产目录 → 可解释命中排行.

Deterministic core: parse the catalog (JSON asset list or Hive-style
DDL), tokenize the query (ASCII words + CJK bigrams), expand through a
built-in zh/en synonym table, and score every asset by weighted matches
— table name > table comment > column name > column comment — returning
an explainable ranking with matched columns and hit locations.  No
database connection.
"""

from .report import render_markdown
from .searcher import (
    Asset,
    SearchHit,
    SearchResult,
    parse_catalog,
    search_assets,
)

__all__ = [
    "Asset",
    "SearchHit",
    "SearchResult",
    "parse_catalog",
    "render_markdown",
    "search_assets",
]
