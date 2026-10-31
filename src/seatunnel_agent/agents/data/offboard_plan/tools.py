"""Chat/MCP tool entry point for the offboarding planner.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def offboard_plan(sql: str, table: str, grace_days: int = 30,
                  lang: str = "") -> str:
    """表下线方案（确定性）：粘贴流水线 SQL + 要下线的表,沿血缘找下游——
    有人在读即判受阻并点名先迁移;随后分四阶段编排：公示时限 → 冻结
    （标 deprecated/停产出,读不受影响）→ 归档快照并核对行数 → 删表
    （归档核验前保持注释,防误执行）。不连调度器与数据库。"""
    from seatunnel_agent.agents.data.offboard_plan import (
        plan_offboard,
        render_markdown,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    if not (table or "").strip():
        return "表名不能为空 / table must not be empty"
    try:
        plan = plan_offboard(sql, table, grace_days=grace_days)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(plan, lang=normalize_lang(lang))
