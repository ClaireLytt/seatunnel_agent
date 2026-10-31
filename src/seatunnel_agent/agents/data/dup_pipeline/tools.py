"""Chat/MCP tool entry point for the duplicate-pipeline detector.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def dup_pipeline(sql: str, fanout: int = 3, lang: str = "") -> str:
    """重复建设检测（确定性）：粘贴多条 INSERT/CREATE 流水线 SQL，按写入
    目标对比各自读什么、算什么——同源双建（输出表达式也一致记高危）、
    子集派生候选、源表高扇出缺中间层,逐项分级。不连调度器与数据库。"""
    from seatunnel_agent.agents.data.dup_pipeline import (
        detect_dup_pipelines,
        render_markdown,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    try:
        report = detect_dup_pipelines(sql, fanout=fanout)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(report, lang=normalize_lang(lang))
