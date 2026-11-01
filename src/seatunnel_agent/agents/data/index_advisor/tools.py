"""Chat/MCP tool entry point for the index advisor.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def index_advisor(queries: str, ddl: str = "", dialect: str = "hive",
                  lang: str = "") -> str:
    """索引与分区推荐（确定性）：粘贴查询集合（多条 SQL），可选表 DDL，
    统计每表每列的等值/范围/join/group 频次，推荐分区列（时间样式且高频
    等值）、分桶列（最热 join key）与组合索引（等值列按频次 + 范围列
    收尾），附命中语句数与可直接改造的 DDL 片段。无法解析的语句会列出
    而不是乱猜。不连数据库。"""
    from seatunnel_agent.agents.data.index_advisor import (
        analyze_workload,
        recommend,
        render_markdown,
    )

    if not (queries or "").strip():
        return "查询集合不能为空 / query workload must not be empty"
    try:
        advice = recommend(analyze_workload(queries, dialect=dialect),
                           ddl_text=ddl)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(advice, lang=normalize_lang(lang))
