"""Chat/MCP tool entry point for the layering checker.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def layer_check(sql: str, layers: str = "", lang: str = "") -> str:
    """数仓分层体检（确定性）：粘贴建表/加工 SQL 脚本，按血缘逐边检查
    分层拓扑 — 跨层引用（ods 直达 dws/ads，跳层越多越重）、反向依赖
    （下层读上层，必高）、同层叠加（dws/ads 层内互读）、未知分层（命名
    对不上前缀）。分层来自命名前缀（内置 ods/stg、dwd/dim、dws/dwm、
    ads/rpt/app），可选 layers 传自定义 JSON（{前缀: 层级}）替换内置。
    不连数据库。"""
    from seatunnel_agent.agents.data.layer_check import (
        parse_layer_map,
        render_markdown,
        run_layer_check,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    try:
        layer_map = (parse_layer_map(layers)
                     if (layers or "").strip() else None)
        result = run_layer_check(sql, layers=layer_map)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
