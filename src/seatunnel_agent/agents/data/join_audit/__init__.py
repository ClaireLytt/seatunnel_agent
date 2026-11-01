"""关联质量审计 — 两份数据行 + 关联键 → 匹配率/孤儿键/爆炸系数.

Deterministic core: parse both sides (sample_profile's parser reused),
build the key tuples, and measure the join itself — match rate per
side, orphan keys, null-key share, and the row explosion a real join
would produce with the worst many-to-many keys named.  Distinct from
data_comparison (same-schema content diff) and rt_offline_diff
(realtime vs offline metrics).  No database connection.
"""

from .auditor import JoinAuditReport, JoinFinding, audit_join, parse_keys
from .report import render_markdown

__all__ = [
    "JoinAuditReport",
    "JoinFinding",
    "audit_join",
    "parse_keys",
    "render_markdown",
]
