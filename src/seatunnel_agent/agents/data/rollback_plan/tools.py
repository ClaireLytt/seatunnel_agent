"""Chat/MCP tool entry point for the rollback planner.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def rollback_plan(sql: str, table: str, partitions: str = "",
                  mode: str = "rerun", snapshot: str = "",
                  lang: str = "") -> str:
    """数据回滚编排（确定性）："表写坏了怎么退"。粘贴流水线 SQL + 坏表
    （可选坏分区,逗号分隔;恢复方式 snapshot/rerun/overwrite,快照表名
    可选），沿血缘向下游分层编排：第 0 步恢复坏表（按方式出模板）、
    逐层重跑下游（层内可并行）、每张涉及表附验证 SQL。不连调度器。"""
    from seatunnel_agent.agents.data.rollback_plan import (
        plan_rollback,
        render_markdown,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    if not (table or "").strip():
        return "表名不能为空 / table must not be empty"
    parts = [p.strip() for p in (partitions or "").split(",") if p.strip()]
    try:
        plan = plan_rollback(sql, table, partitions=parts, mode=mode,
                             snapshot=snapshot)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(plan, lang=normalize_lang(lang))
