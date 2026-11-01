"""任务失败归因 — 失败任务导出 → 错误归类、同根因聚类与重试判定.

Deterministic core: classify every failure by its error text
(dependency missing / resource / timeout / connection / data error /
code error), cluster identical normalized error signatures into one
root-cause group, judge whether retrying helped (transient / futile /
mixed), and prescribe per class.  No scheduler connection.
"""

from .classifier import (
    FailedTask,
    FailureCluster,
    FailureResult,
    classify_failures,
    parse_failures,
)
from .report import render_markdown

__all__ = [
    "FailedTask",
    "FailureCluster",
    "FailureResult",
    "classify_failures",
    "parse_failures",
    "render_markdown",
]
