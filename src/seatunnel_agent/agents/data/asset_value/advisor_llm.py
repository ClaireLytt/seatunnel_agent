"""Optional LLM grading note from an asset-value result.

The deterministic grader scores and tiers the assets; this layer turns
the grading into a paste-ready note for the governance channel.
Strictly opt-in and bounded to one call per grading.
"""

from __future__ import annotations

import json

from .valuer import ValueResult

__all__ = ["grading_note"]

_SYSTEM_ZH = (
    "你是数据平台的资产治理值班。根据给定的资产价值评估 JSON（各资产的"
    "分数、层级、价值×成本象限、证据：访问/依赖/新近度），起草一条发给"
    "治理群的评估通报：核心资产是哪些、低价值高成本的清理候选是哪些、"
    "建议的下一步（清理走存储成本治理、核心表补副本与 SLA）。只输出"
    "通报正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-governance on-call. From the given asset-value "
    "JSON (per asset: score, tier, value x cost quadrant, evidence of "
    "access/dependencies/recency), draft a governance-channel note: the "
    "core assets, the low-value high-cost cleanup candidates, and next "
    "steps (cleanup via the storage-cost agent, replication/SLA review "
    "for core tables). Markdown body only, terse.")


def grading_note(result: ValueResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready grading note."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("asset_value", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
