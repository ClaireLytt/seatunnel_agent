"""Chat/MCP tool entry point for the DAG optimizer agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def dag_optimize(dag: str, base: str = "", deadline: str = "",
                 lang: str = "") -> str:
    """DAG 依赖优化（确定性）：粘贴任务依赖图（JSON tasks/edges、Graphviz DOT 或
    ``a -> b`` 文本行，任务可带 duration），用传递归约找出不必要的串行
    依赖边并给出替代路径依据，按 Kahn 分层给出可并行的批次与最大并行度，
    按任务时长计算关键路径与理想加速比，并提示可合并的单进单出串行链。
    可选 deadline（SLA 时长）：判定是否满足，不满足时给出按收益排序的
    最小提速任务集合。可选 base（基线 DAG，格式同 dag）：额外输出变更
    评审——增删的任务与边、关键路径与 2 并发工期变化、新引入的冗余。
    不连调度器，不连数据库。"""
    from seatunnel_agent.agents.data.dag_optimize import (
        diff_dags,
        optimize,
        parse_dag,
        render_diff_markdown,
        render_markdown,
    )

    if not (dag or "").strip():
        return "任务依赖图不能为空 / DAG input must not be empty"
    try:
        sla = float(deadline) if (deadline or "").strip() else 0.0
        graph = parse_dag(dag)
        result = optimize(graph, deadline=sla)
        diff_md = ""
        if (base or "").strip():
            diff = diff_dags(parse_dag(base), graph, after=result)
            diff_md = render_diff_markdown(
                diff, lang=normalize_lang(lang)) + "\n"
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # json errors etc.
        return f"输入有误 / bad input: {exc}"
    return diff_md + render_markdown(result, lang=normalize_lang(lang))
