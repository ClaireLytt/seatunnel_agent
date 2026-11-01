"""权限申请审核 — 申请单 × 敏感级词表 → 风险分与批准/降级/拒绝.

Deterministic core: grade the requested columns against a built-in
sensitivity vocabulary (S3 direct identifiers and money, S2
quasi-identifiers), accrue risk from wildcards, write-for-read roles,
long terms and thin purposes, and decide approve / downgrade (with the
concrete cuts) / reject — transparently, per application.  No database
connection.
"""

from .report import render_markdown
from .reviewer import (
    GrantReview,
    ReviewResult,
    parse_applications,
    parse_vocabulary,
    review_grants,
)

__all__ = [
    "GrantReview",
    "ReviewResult",
    "parse_applications",
    "parse_vocabulary",
    "render_markdown",
    "review_grants",
]
