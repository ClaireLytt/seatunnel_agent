"""Chat/MCP tool entry point for the asset-value grader.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def asset_value(inventory: str, lang: str = "") -> str:
    """数据资产价值评估（确定性）：粘贴资产清单（CSV 表头 table,size_gb,
    access_cnt_30d,last_access,downstream_cnt 或同字段 JSON），透明打分 —
    30 天访问最高 50 分（对数）、下游依赖最高 30 分、新近度最高 20 分，
    分层核心/常用/边缘/闲置（60/35/15），并按大小中位数给出价值×成本
    四象限；「低价值·高成本」即清理候选。不连数据库。"""
    from seatunnel_agent.agents.data.asset_value import (
        parse_inventory,
        render_markdown,
        value_assets,
    )

    if not (inventory or "").strip():
        return "资产清单不能为空 / inventory must not be empty"
    try:
        result = value_assets(parse_inventory(inventory))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
