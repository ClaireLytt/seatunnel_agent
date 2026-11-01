"""Optional LLM tightening suggestions for a DQC rule draft.

The deterministic generator only promises what the sample keeps; this
layer suggests where the draft is weaker than the business needs.
Strictly opt-in and bounded to one call per draft.  Only check metadata
is sent — never the rows.
"""

from __future__ import annotations

import json

from .generator import RuleDraft

__all__ = ["tighten_note"]

_SYSTEM_ZH = (
    "你是数据质量评审。给定一份由样例自动生成的 DQC 规则草稿 JSON"
    "（逐列检查与依据、跳过的列 — 不含数据行），指出草稿偏松的地方并给"
    "出收紧建议：哪些列名看起来是主键该补 unique、哪些枚举集可能不全、"
    "哪些空值余量该砍、row_count 变化阈值是否合适。只输出建议 markdown "
    "列表，每条一句，不要寒暄。")
_SYSTEM_EN = (
    "You are a data-quality reviewer. Given an auto-drafted DQC rule "
    "set (per-column checks with their basis, skipped columns — no "
    "rows included), point out where the draft is looser than the "
    "business needs: key-looking columns missing a unique check, enum "
    "sets that may be incomplete, null head-rooms worth cutting, "
    "whether the row-count change guard fits. Markdown bullets, one "
    "sentence each, terse.")


def tighten_note(draft: RuleDraft, lang: str = "zh") -> str:
    """One LLM call → tightening suggestions; rows never leave."""
    from seatunnel_agent.common.llm import one_shot

    meta = draft.to_dict()
    meta.pop("yaml_text", None)
    return one_shot("dq_rulegen", _SYSTEM_ZH, _SYSTEM_EN,
                    json.dumps(meta, ensure_ascii=False), lang)
