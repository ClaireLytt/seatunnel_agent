"""Chat/MCP tool entry point for the rerun planner agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def rerun_plan(dag: str, failed: str, succeeded: str = "",
               cmd: str = "", lang: str = "") -> str:
    """任务重跑规划（确定性）：粘贴任务依赖图（JSON tasks/edges 或
    ``a -> b`` 文本行）和失败任务名（逗号分隔），重跑集合 = 失败任务 +
    其下游闭包，上游产出保留、兄弟分支不动；可选已成功任务列表（闭包内
    曾成功的任务因输入失效仍会标记重跑），按拓扑批次输出并给出影响面。
    可选命令模板用 {task} 渲染重跑命令。不连调度器，不连数据库。"""
    from seatunnel_agent.agents.data.rerun_plan import (
        parse_dag,
        plan_rerun,
        render_markdown,
    )

    if not (dag or "").strip():
        return "任务依赖图不能为空 / DAG input must not be empty"
    if not (failed or "").strip():
        return "失败任务不能为空 / failed tasks must not be empty"
    try:
        result = plan_rerun(parse_dag(dag), failed, succeeded)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # json errors etc.
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang),
                           cmd_template=cmd)
