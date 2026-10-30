"""Optional LLM action plan from a DAG analysis.

The deterministic analysis quantifies redundancy, bottlenecks,
makespans and the SLA verdict; this layer turns the numbers into a
prioritized to-do list for the scheduler owner.  Strictly opt-in,
one bounded call.
"""

from __future__ import annotations

import json

from .optimizer import DagOptimizeResult

__all__ = ["action_plan"]

_SYSTEM_ZH = (
    "你是调度平台负责人。根据给定的 DAG 分析 JSON（冗余边、并行批次、"
    "关键路径、瓶颈敏感度、各并发 makespan、SLA 判定），写一份按收益"
    "排序的优化行动清单：每条行动写清改什么、预期收益（引用 JSON 里的"
    "数字）、风险。只输出 markdown 列表，务实，不要寒暄。")
_SYSTEM_EN = (
    "You own the scheduler. From the given DAG analysis JSON (redundant "
    "edges, waves, critical path, bottleneck sensitivity, makespans per "
    "worker count, SLA verdict), write a prioritized action list: each "
    "item states the change, the expected gain (cite the JSON numbers) "
    "and the risk. Markdown list only, pragmatic, no pleasantries.")


def action_plan(result: DagOptimizeResult, lang: str = "zh") -> str:
    """One LLM call → the prioritized optimisation to-do list."""
    from seatunnel_agent.common.config import load_settings
    from seatunnel_agent.common.llm import LLMClient

    client = LLMClient(load_settings(), agent="dag_optimize")
    data = result.to_dict()
    data.pop("optimized", None)  # long and derivable — not needed
    payload = json.dumps(data, ensure_ascii=False)
    system = _SYSTEM_ZH if lang == "zh" else _SYSTEM_EN
    resp = client.chat(system, [{"role": "user", "content": payload}])
    return resp.reply_text.strip()
