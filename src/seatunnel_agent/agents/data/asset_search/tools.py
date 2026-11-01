"""Chat/MCP tool entry point for the asset searcher.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def asset_search(catalog: str, query: str, lang: str = "") -> str:
    """数据资产搜索（确定性）：粘贴资产目录（JSON 清单 [{table, comment,
    columns:[{name,comment}]}] 或 Hive 风格建表 DDL）+ 自然语言业务需求，
    分词 + 中英同义词扩展后加权检索（表名 > 表注释 > 列名 > 列注释），
    返回可解释的命中排行：每张表的分数、命中列与命中位置。不连数据库。"""
    from seatunnel_agent.agents.data.asset_search import (
        parse_catalog,
        render_markdown,
        search_assets,
    )

    if not (catalog or "").strip():
        return "资产目录不能为空 / catalog must not be empty"
    if not (query or "").strip():
        return "查询不能为空 / query must not be empty"
    try:
        result = search_assets(parse_catalog(catalog), query)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed JSON/DDL
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
