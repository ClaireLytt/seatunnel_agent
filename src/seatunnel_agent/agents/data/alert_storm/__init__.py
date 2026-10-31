"""告警风暴聚合 — 告警导出 → 签名聚类、风暴窗口与抑制建议.

Deterministic core: cluster alerts by a normalized title signature (one
root cause, one row), surface the dedup ratio, and judge the channel —
storm windows against the median bucket, flapping signatures inside an
hour, and noisy sources — each with a prescription.  No
alerting-system connection.
"""

from .analyzer import (
    Alert,
    AlertCluster,
    AsFinding,
    StormResult,
    analyze_alerts,
    parse_alerts,
)
from .report import render_markdown

__all__ = [
    "Alert",
    "AlertCluster",
    "AsFinding",
    "StormResult",
    "analyze_alerts",
    "parse_alerts",
    "render_markdown",
]
