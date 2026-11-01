"""时间戳体检 — 数据行 → 时区/单位/哨兵的逐列审计.

Deterministic core: parse the rows (sample_profile's parser reused) and
audit every timestamp-shaped column for the four silent corruptions —
explicit-offset disagreement in one column (direct evidence), epoch
seconds mixed with milliseconds, the ~8h bimodal hour histogram (the
UTC-vs-local smell, an honest heuristic), and sentinel years outside
1980..2100.  dist_anomaly profiles numeric distributions; this reads
timestamp meaning.  No database connection.
"""

from .auditor import TimezoneAudit, TzFinding, audit_timezones
from .report import render_markdown

__all__ = [
    "TimezoneAudit",
    "TzFinding",
    "audit_timezones",
    "render_markdown",
]
