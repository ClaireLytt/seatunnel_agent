"""Optional LLM modeling review from a model report.

The deterministic reviewer names the structural findings; this layer
drafts the refactoring advice a senior modeler would give.  Strictly
opt-in and bounded to one call per report.
"""

from __future__ import annotations

import json

from .reviewer import ModelReport

__all__ = ["modeling_note"]

_SYSTEM_ZH = (
    "你是数仓建模评审。给定一份维度建模体检 JSON（表角色统计与分级发现："
    "维表缺主键、事实表缺分区或外键、维度属性混入事实表、属性跨事实表复制、"
    "汇总表无度量、宽表），给出改造建议：先修哪张表、属性下沉到哪张维表、"
    "拆分怎么切。只输出建议 markdown 列表，按收益排序，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are a warehouse modeling reviewer. Given a dimensional-model "
    "review JSON (table roles and graded findings: keyless dimensions, "
    "unpartitioned or dimension-less facts, descriptive attributes "
    "inside facts, attributes copied across facts, measure-less "
    "aggregates, over-wide tables), give the refactoring advice: which "
    "table to fix first, where each attribute should sink, how a split "
    "should cut. Markdown bullets only, ordered by payoff, terse.")


def modeling_note(report: ModelReport, lang: str = "zh") -> str:
    """One LLM call → refactoring advice for this review."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(report.to_dict(), ensure_ascii=False)
    return one_shot("model_review", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
