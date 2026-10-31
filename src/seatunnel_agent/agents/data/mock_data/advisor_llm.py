"""Optional LLM dataset note from a mock-data result.

The deterministic generator decides every value; this layer drafts the
README that travels with the dataset.  Strictly opt-in and bounded to
one call per generation.  Only the column strategies are sent — never
the rows.
"""

from __future__ import annotations

import json

from .generator import MockResult

__all__ = ["dataset_note"]

_SYSTEM_ZH = (
    "你是测试数据管理员。给定一份 mock 数据集的逐列生成策略 JSON（序列/"
    "区间/日期窗口/枚举分布/合成敏感值 — 不含数据行），起草随数据集"
    "交付的说明：每列怎么来的、哪些列是合成假值、适合与不适合什么测试"
    "场景。只输出说明 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the test-data steward. Given the per-column generation "
    "strategies of a mock dataset (sequences, ranges, date windows, "
    "enum distributions, synthesized sensitive values — no rows "
    "included), draft the README that ships with the dataset: how each "
    "column was produced, which are synthetic fakes, what test "
    "scenarios it suits and does not. Markdown only, terse.")


def dataset_note(result: MockResult, lang: str = "zh") -> str:
    """One LLM call → a dataset README; rows never leave the process."""
    from seatunnel_agent.common.llm import one_shot

    meta = {"rows_generated": result.rows_generated, "seed": result.seed,
            "plans": [p.to_dict() for p in result.plans]}
    payload = json.dumps(meta, ensure_ascii=False)
    return one_shot("mock_data", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
