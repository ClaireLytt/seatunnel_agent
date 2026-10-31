"""Optional LLM business descriptions on top of the dictionary skeleton.

The deterministic generator builds the structure; this layer drafts the
per-column business descriptions the comments are missing.  Strictly
opt-in and bounded to one call per dictionary.
"""

from __future__ import annotations

import json

from .generator import DictResult

__all__ = ["describe_columns"]

_SYSTEM_ZH = (
    "你是数据平台的元数据管理员。根据给定的数据字典骨架 JSON（每表每列的"
    "名称、推断角色、已有注释、SQL 使用频次），为注释为空的列草拟一句话"
    "业务描述（结合列名、角色与同表上下文），已有注释的列不要改写。输出 "
    "markdown 列表：`表.列` — 描述。只输出列表，不要寒暄。")
_SYSTEM_EN = (
    "You are the metadata steward. From the given dictionary-skeleton "
    "JSON (per table/column: name, inferred role, existing comment, SQL "
    "usage counts), draft a one-line business description for every "
    "column whose comment is empty (use the name, role and table "
    "context); never rewrite existing comments. Output a markdown list: "
    "`table.column` — description. List only.")


def describe_columns(result: DictResult, lang: str = "zh") -> str:
    """One LLM call → drafted descriptions for the uncommented columns."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("data_dict", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
