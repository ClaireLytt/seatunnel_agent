"""Chat/MCP tool entry point for the rerun planner agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def rerun_plan(dag: str, failed: str = "", succeeded: str = "",
               statuses: str = "", cmd: str = "", lang: str = "") -> str:
    """任务重跑规划（确定性）：粘贴任务依赖图（JSON tasks/edges、Graphviz DOT 或
    ``a -> b`` 文本行）和失败任务名（逗号分隔），重跑集合 = 失败任务 +
    其下游闭包，上游产出保留、兄弟分支不动；可选已成功任务列表（闭包内
    曾成功的任务因输入失效仍会标记重跑），按拓扑批次输出并给出影响面。
    也可直接粘贴调度器状态导出 statuses（``{"task":"state"}`` JSON 或
    ``task=state`` 行，failed/success 自动归类）代替手填两个列表。
    可选命令模板用 {task} 渲染重跑命令。不连调度器，不连数据库。"""
    from seatunnel_agent.agents.data.rerun_plan import (
        parse_dag,
        parse_statuses,
        plan_rerun,
        render_markdown,
    )

    if not (dag or "").strip():
        return "任务依赖图不能为空 / DAG input must not be empty"
    if not (failed or "").strip() and not (statuses or "").strip():
        return ("失败任务或状态导出不能为空 / "
                "failed tasks or statuses must not be empty")
    try:
        if (statuses or "").strip():
            failed_list, ok_list = parse_statuses(statuses)
            result = plan_rerun(parse_dag(dag), failed_list, ok_list)
        else:
            result = plan_rerun(parse_dag(dag), failed, succeeded)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # json errors etc.
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang),
                           cmd_template=cmd)
