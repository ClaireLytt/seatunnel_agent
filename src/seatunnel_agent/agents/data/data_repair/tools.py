"""Chat/MCP tool entry point for the consistency-repair planner.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def data_repair(data: str, table: str = "<table>", pk: str = "",
                biz_key: str = "", lang: str = "") -> str:
    """数据一致性修复（确定性）：粘贴 CSV（带表头）或 JSONL 数据行 +
    目标表名（可选主键/业务键），自动跑重复检测与抽样剖析，为每个确认的
    问题生成可复制的修复 SQL 模板 — ROW_NUMBER 去重、COALESCE 空值
    回填、TRIM/LOWER 标准化、千分位/货币符清洗转数值、离群格式改写；
    <尖括号> 占位符留给人工决策。不连数据库。"""
    from seatunnel_agent.agents.data.data_repair import (
        plan_repairs,
        render_markdown,
    )

    if not (data or "").strip():
        return "数据不能为空 / data must not be empty"
    try:
        plan = plan_repairs(data, table=table or "<table>",
                            pk=pk or None, biz_key=biz_key or None)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(plan, lang=normalize_lang(lang))
