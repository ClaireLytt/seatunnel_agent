"""Optional LLM scheduling review from a DAG draft.

The deterministic generator wires the tasks; this layer drafts the
pre-deploy review — sensors, retries, pools, schedule fit.  Strictly
opt-in and bounded to one call per draft.
"""

from __future__ import annotations

import json

from .generator import DagDraft

__all__ = ["schedule_note"]

_SYSTEM_ZH = (
    "你是调度平台评审。给定一份自动生成的 Airflow DAG 草稿 JSON（任务与"
    "依赖边、脚本外上游表、调度表达式），起草部署前评审：哪些外部上游"
    "该挂什么 sensor、重试与超时参数怎么配、调度时间与上游产出是否错"
    "峰、哪些任务可并行池化。只输出评审 markdown 列表，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are a scheduler-platform reviewer. Given an auto-drafted "
    "Airflow DAG JSON (tasks and edges, external upstream tables, the "
    "schedule), draft the pre-deploy review: which sensors the external "
    "upstreams need, retry and timeout settings, whether the schedule "
    "clears upstream landing times, which tasks can share a pool. "
    "Markdown bullets only, terse.")


def schedule_note(draft: DagDraft, lang: str = "zh") -> str:
    """One LLM call → a pre-deploy review for this DAG draft."""
    from seatunnel_agent.common.llm import one_shot

    meta = draft.to_dict()
    meta.pop("python_text", None)
    return one_shot("dag_gen", _SYSTEM_ZH, _SYSTEM_EN,
                    json.dumps(meta, ensure_ascii=False), lang)
