"""Optional LLM recommendation from an asset-search result.

The deterministic retriever ranks the candidates; this layer picks and
explains the best fit for the stated business need.  Strictly opt-in and
bounded to one call per search.
"""

from __future__ import annotations

import json

from .searcher import SearchResult

__all__ = ["recommend_note"]

_SYSTEM_ZH = (
    "你是数据平台的找数助手。根据给定的资产检索 JSON（业务查询、检索词、"
    "按分数排序的命中表：表注释、命中列、命中位置），为这个业务需求推荐"
    "最合适的一张或两张表：为什么选它、该用哪些列、有什么使用注意"
    "（口径/粒度）。只输出推荐正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-discovery assistant. From the given asset-search "
    "JSON (the business query, terms, hits ranked by score with table "
    "comments, matched columns and hit locations), recommend the one or "
    "two best-fit tables: why, which columns to use, and any caliber or "
    "grain cautions. Markdown body only, terse.")


def recommend_note(result: SearchResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready recommendation for this search."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("asset_search", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
