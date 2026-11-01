"""Optional LLM reconciliation note from a realtime-offline diff.

The deterministic comparator aligns and judges; this layer turns the
result into a paste-ready note for the data-owner channel.  Strictly
opt-in and bounded to one call per comparison.
"""

from __future__ import annotations

import json

from .comparator import DiffResult

__all__ = ["recon_note"]

_SYSTEM_ZH = (
    "你是数据平台的口径值班。根据给定的实时-离线核对 JSON（对齐数、"
    "一致率、双侧缺失键、超容差差异、系统性偏差判定），起草一条发给"
    "双方负责人的核对通报：差在哪、是零星差异还是系统性偏差、最可能的"
    "口径/链路解释（迟到数据/窗口未闭/重复消费/口径不一致）、建议的"
    "下一步。只输出通报正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-caliber on-call. From the given realtime-offline "
    "reconciliation JSON (matched keys, consistency rate, missing keys "
    "on both sides, over-tolerance mismatches, systematic-bias "
    "verdicts), draft a note for both owners: where the gap is, whether "
    "it is sporadic or systematic, the likely explanation (late data / "
    "unclosed windows / duplicate consumption / caliber drift), and the "
    "next step. Markdown body only, terse.")


def recon_note(result: DiffResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready reconciliation note."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("rt_offline_diff", _SYSTEM_ZH, _SYSTEM_EN, payload,
                    lang)
