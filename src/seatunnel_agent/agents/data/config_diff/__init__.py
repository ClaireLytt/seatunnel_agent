"""配置漂移对比 — 两份作业配置 → 按风险分级的语义差异.

Deterministic core: parse both sides through pyhocon (SeaTunnel HOCON,
JSON and flat properties all work), flatten to dotted keys, and grade
every added / removed / changed key by what it controls — throughput,
state and data-destination keys high; tuning knobs mid.  Secret-shaped
values are masked but their changes still count.  No environment
connection.
"""

from .differ import (
    ConfigDiffResult,
    DiffEntry,
    diff_configs,
    flatten_config,
    parse_config,
)
from .report import render_markdown

__all__ = [
    "ConfigDiffResult",
    "DiffEntry",
    "diff_configs",
    "flatten_config",
    "parse_config",
    "render_markdown",
]
