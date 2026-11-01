"""增量同步策略推荐 — 源表更新特征 → 全量 / 增量 / CDC.

Deterministic core: parse the per-source-table characteristics
inventory (JSON or CSV — row count, daily changed rows, update
timestamp, primary key, physical deletes, CDC availability, latency
requirement) and recommend a sync strategy per table — full reload,
timestamp incremental, PK incremental or CDC — with the rule trace as
reasons and the residual risks.  No database connection.
"""

from .advisor import (
    Recommendation,
    SourceTable,
    StrategyReport,
    parse_tables,
    recommend,
)
from .config_stub import config_stub
from .ddl import tables_from_ddl
from .report import render_markdown

__all__ = [
    "Recommendation",
    "SourceTable",
    "StrategyReport",
    "config_stub",
    "parse_tables",
    "recommend",
    "render_markdown",
    "tables_from_ddl",
]
