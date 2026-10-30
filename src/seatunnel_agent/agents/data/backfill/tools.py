"""Chat/MCP tool entry point for the backfill planner agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def backfill_plan(events: str, rules: str = "", sql_dir: str = "",
                  now: str = "", since: str = "", lang: str = "") -> str:
    """补数计划（确定性）：粘贴表更新事件清单（JSON 或 CSV，字段
    table/updated），可选规则 JSON 与血缘 SQL 目录，按分区网格找出每张表的
    缺失分区，沿血缘下游级联出需要重跑的表和日期，并给出拓扑批次顺序。
    now 默认取清单里最晚的更新时间。不连数据库，不连调度器。"""
    from seatunnel_agent.agents.data.backfill import plan, render_markdown
    from seatunnel_agent.agents.data.data_freshness import (
        parse_events,
        parse_rules,
    )

    if not (events or "").strip():
        return "更新事件不能为空 / update events must not be empty"
    graph = None
    if sql_dir.strip():
        from pathlib import Path

        if not Path(sql_dir.strip()).is_dir():
            return f"血缘目录不存在 / not a directory: {sql_dir.strip()}"
        from seatunnel_agent.agents.data.data_lineage.loaders import (
            from_sql_dir,
        )

        graph, _ = from_sql_dir(sql_dir.strip())
    try:
        result = plan(parse_events(events), parse_rules(rules), graph=graph,
                      now=now.strip() or None, since=since.strip() or None)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
