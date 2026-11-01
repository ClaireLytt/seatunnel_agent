"""Chat/MCP tool entry point for the DAG drafter.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def dag_gen(sql: str, dag_id: str = "pipeline",
            schedule: str = "0 2 * * *", lang: str = "") -> str:
    """Airflow DAG 草稿生成（确定性）：粘贴多条 INSERT/CREATE 流水线 SQL,
    每个写入目标生成一个任务,目标互读自动连依赖边,脚本外上游表在注释里
    点名该挂 sensor 的位置;产出 ast.parse 零错误的 dag.py 骨架,替换
    <RUN> 占位符即可部署。dag_check 诊断图,本工具出文件。不连调度器。"""
    from seatunnel_agent.agents.data.dag_gen import (
        generate_dag,
        render_markdown,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    try:
        draft = generate_dag(sql, dag_id=dag_id, schedule=schedule)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(draft, lang=normalize_lang(lang))
