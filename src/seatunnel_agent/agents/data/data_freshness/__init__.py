"""数据新鲜度监控 — 表更新事件清单(JSON/CSV)的迟到/断更/过期判定.

Deterministic core: parse per-table update events (table, updated
timestamps), take the expected cadence from optional rules or infer it
as the median historical gap, and judge every table at a reproducible
"now" (default: the latest update seen): stalled (no new output),
stale (over max_age) or late (behind schedule). No database connection —
works on partition listings, scheduler exports or any equivalent dump.
"""

from .checker import (
    SEVERITY,
    FreshnessScan,
    TableFreshness,
    parse_duration,
    parse_events,
    parse_rules,
    scan,
)
from .report import render_markdown, scan_to_dict

__all__ = [
    "SEVERITY",
    "FreshnessScan",
    "TableFreshness",
    "parse_duration",
    "parse_events",
    "parse_rules",
    "render_markdown",
    "scan",
    "scan_to_dict",
]
