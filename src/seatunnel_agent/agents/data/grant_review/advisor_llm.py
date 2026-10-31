"""Optional LLM review note from a grant review.

The deterministic reviewer scores and decides; this layer drafts the
reply to the applicants.  Strictly opt-in and bounded to one call per
review batch.
"""

from __future__ import annotations

import json

from .reviewer import ReviewResult

__all__ = ["review_note"]

_SYSTEM_ZH = (
    "你是数据平台的权限审批人。根据给定的审核 JSON（每份申请的风险分、"
    "结论、风险点、降级建议），为每份申请起草一句话回复：批准的说明"
    "期限与范围；降级批准的说明给了什么、砍了什么、为什么；拒绝的说明"
    "补齐什么可以重新申请。输出 markdown 列表：申请人 — 回复。只输出"
    "列表，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-permission approver. From the given review JSON "
    "(per application: risk, decision, factors, downgrades), draft a "
    "one-line reply per application: approvals state the term and scope; "
    "downgraded approvals state what was granted, what was cut and why; "
    "rejections state what to fix before reapplying. Output a markdown "
    "list: applicant — reply. List only.")


def review_note(result: ReviewResult, lang: str = "zh") -> str:
    """One LLM call → paste-ready replies for this review batch."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("grant_review", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
