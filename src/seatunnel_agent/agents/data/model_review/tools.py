"""Chat/MCP tool entry point for the model reviewer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def model_review(sql: str, wide_limit: int = 50, lang: str = "") -> str:
    """维度建模体检（确定性）：粘贴 CREATE TABLE DDL，按前缀识别表角色
    （dim 维表 / dwd·dws 事实 / ods·stg 原始）后体检星型结构——维表缺
    主键（高）、事实表缺分区或缺 *_id 外键、描述性属性混入事实表、属性
    跨事实表复制、汇总表无度量、宽表。不读数据。"""
    from seatunnel_agent.agents.data.model_review import (
        render_markdown,
        review_model,
    )

    if not (sql or "").strip():
        return "DDL 不能为空 / DDL must not be empty"
    try:
        report = review_model(sql, wide_limit=wide_limit)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(report, lang=normalize_lang(lang))
