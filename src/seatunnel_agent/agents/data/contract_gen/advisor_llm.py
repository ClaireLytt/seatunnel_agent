"""Optional LLM tightening suggestions for a contract draft.

The deterministic generator only promises what the DDL already keeps;
this layer suggests where the draft is weaker than it should be.
Strictly opt-in and bounded to one call per draft.
"""

from __future__ import annotations

import json

from .generator import ContractDraft

__all__ = ["tighten_note"]

_SYSTEM_ZH = (
    "你是数据契约评审。给定一份由 DDL 自动生成的数据契约草稿 JSON"
    "（逐表列清单、分区、注释规则、注释覆盖率），指出草稿偏松的地方并"
    "给出收紧建议：哪些表应当 allow_extra_columns: false、哪些表注释"
    "覆盖率低该补注释、哪些列名看起来是对外口径该显式声明类型。只输出"
    "建议 markdown 列表，每条一句，不要寒暄。")
_SYSTEM_EN = (
    "You are a data-contract reviewer. Given a contract draft "
    "auto-generated from DDL (per-table columns, partitions, comment "
    "rules, comment coverage), point out where the draft is looser than "
    "it should be: which tables deserve allow_extra_columns: false, "
    "which have poor comment coverage worth fixing, and which columns "
    "look like public-facing metrics that should pin a type. Markdown "
    "bullet list only, one sentence each, terse.")


def tighten_note(draft: ContractDraft, lang: str = "zh") -> str:
    """One LLM call → tightening suggestions for this draft."""
    from seatunnel_agent.common.llm import one_shot

    payload = draft.to_dict()
    payload.pop("yaml_text", None)   # the structure is enough
    return one_shot("contract_gen", _SYSTEM_ZH, _SYSTEM_EN,
                    json.dumps(payload, ensure_ascii=False), lang)
