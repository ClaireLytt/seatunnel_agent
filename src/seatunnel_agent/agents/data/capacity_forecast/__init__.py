"""容量耗尽预测 — 存储序列 × 配额 → 耗尽日期、增长大户与缩小指标.

Deterministic core: reuse the data_volatility series parser, fit a
least-squares slope per metric over the recent window, project the
total against the quota (linear extrapolation, stated openly) to the
exhaustion date with 90/30-day alarms, and rank the top growers and
shrinking metrics.  No storage connection.
"""

from .forecaster import (
    CapacityResult,
    CfFinding,
    MetricTrend,
    forecast_capacity,
)
from .report import render_markdown

__all__ = [
    "CapacityResult",
    "CfFinding",
    "MetricTrend",
    "forecast_capacity",
    "render_markdown",
]
