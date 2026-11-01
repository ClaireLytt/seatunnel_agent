"""Optional LLM landing review from a DDL draft.

The deterministic converter maps the types; this layer drafts the
landing review.  Strictly opt-in and bounded to one call per draft.
"""

from __future__ import annotations

import json

from .converter import DdlDraft

__all__ = ["landing_note"]

_SYSTEM_ZH = (
    "你是数据接入评审。给定一份消息 Schema 建表草稿 JSON（源类型到 DDL "
    "类型的逐列映射、有损映射清单、目标方言），起草落地评审：有损行各自"
    "该怎么处置（上游拆 union/建子表装复杂类型）、Doris 的 key 与分桶怎么"
    "按业务改、建表后该补哪些闸（契约/DQC）。只输出评审 markdown 列表，"
    "简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are a data-landing reviewer. Given a schema-to-DDL draft JSON "
    "(per-column type mapping, lossy rows, target dialect), draft the "
    "landing review: how to treat each lossy row (split the union "
    "upstream, child tables for complex types), how the Doris key and "
    "buckets should change for the business, and which gates (contract, "
    "DQC) to add after the table lands. Markdown bullets only, terse.")


def landing_note(draft: DdlDraft, lang: str = "zh") -> str:
    """One LLM call → a landing review for this draft."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(draft.to_dict(), ensure_ascii=False)
    return one_shot("avro2ddl", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
