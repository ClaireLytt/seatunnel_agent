"""EN/ZH strings for the asset-search reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

AS_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Asset Search",
        "rpt_scope": "query “{query}” over **{total}** asset(s) · "
                     "terms: {terms}",
        "rpt_hits": "Matches (best first)",
        "col_rank": "#",
        "col_table": "table",
        "col_score": "score",
        "col_cols": "matched columns",
        "col_why": "hit on",
        "rpt_no_hits": "Nothing matched — try other words, or enrich the "
                       "catalog comments (the data-dict agent drafts "
                       "them).",
        "rpt_disclaimer": "> Deterministic keyword + synonym retrieval, "
                          "weighted table name > table comment > column "
                          "name > column comment. Ranking is explainable "
                          "via the hit list.",
        "rpt_llm_note": "Recommendation (LLM — review before relying "
                        "on it)",
    },
    "zh": {
        "rpt_title": "数据资产搜索",
        "rpt_scope": "查询「{query}」· 共 **{total}** 个资产 · "
                     "检索词：{terms}",
        "rpt_hits": "命中（分数高在前）",
        "col_rank": "#",
        "col_table": "表",
        "col_score": "分数",
        "col_cols": "命中列",
        "col_why": "命中位置",
        "rpt_no_hits": "没有命中 — 换个说法，或先补全目录注释"
                       "（数据字典 agent 可以代笔）。",
        "rpt_disclaimer": "> 确定性关键词 + 同义词检索，加权 表名 > 表注释 "
                          "> 列名 > 列注释；命中清单让排序可解释。",
        "rpt_llm_note": "推荐说明（LLM — 采信前请复核）",
    },
}

tp = make_lookup(AS_I18N)
