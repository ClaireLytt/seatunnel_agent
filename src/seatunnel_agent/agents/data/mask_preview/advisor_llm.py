"""Optional LLM masking-policy note from a mask preview.

The deterministic masker picks the rules; this layer drafts the policy
note that goes with the masked extract.  Strictly opt-in and bounded to
one call per preview.  Only rule metadata is sent — never the rows.
"""

from __future__ import annotations

import json

from .masker import MaskPreview

__all__ = ["policy_note"]

_SYSTEM_ZH = (
    "你是数据安全评审。给定一份脱敏预览的规则元数据 JSON（命中的敏感列、"
    "类别、判定依据、严重级 — 不含任何数据值），起草随脱敏样例外发的策略"
    "说明：各列用了什么规则、残余风险在哪、收数方注意什么。只输出说明 "
    "markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are a data-security reviewer. Given the rule metadata JSON of "
    "a masking preview (detected sensitive columns, categories, "
    "detection basis, severities — no data values included), draft the "
    "policy note that travels with the masked extract: which rule each "
    "column got, the residual risks, what the receiving side must "
    "observe. Markdown only, terse.")


def policy_note(preview: MaskPreview, lang: str = "zh") -> str:
    """One LLM call → a policy note; rows never leave the process."""
    from seatunnel_agent.common.llm import one_shot

    meta = {"rows_total": preview.rows_total,
            "columns": [{"name": c.name, "category": c.category,
                         "severity": c.severity,
                         "detected_by": c.detected_by}
                        for c in preview.columns]}
    payload = json.dumps(meta, ensure_ascii=False)
    return one_shot("mask_preview", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
