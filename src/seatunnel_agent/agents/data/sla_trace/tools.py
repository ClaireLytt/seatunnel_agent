"""Chat/MCP tool entry point for the SLA trace agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def sla_trace(instances: str, target: str = "", deadline: str = "",
              lang: str = "") -> str:
    """调度依赖延迟分析（确定性）：粘贴一轮调度的任务实例导出
    （JSON 数组或 CSV，字段 name/start/end/deps），计算到目标任务的
    关键路径，按"等依赖 vs 自身运行"归因每个任务的延迟；给 deadline
    时附 SLA 达标/破线结论。不连调度器。"""
    from seatunnel_agent.agents.data.sla_trace import (
        parse_instances,
        render_markdown,
        trace,
    )

    if not (instances or "").strip():
        return "任务实例不能为空 / task instances must not be empty"
    try:
        result = trace(parse_instances(instances), target=target.strip(),
                       deadline=deadline.strip() or None)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
