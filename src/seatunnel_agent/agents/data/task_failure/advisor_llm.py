"""Optional LLM failure note from a task-failure attribution.

The deterministic classifier clusters the failures; this layer turns the
clusters into a paste-ready note for the ops channel.  Strictly opt-in
and bounded to one call per attribution.
"""

from __future__ import annotations

import json

from .classifier import FailureResult

__all__ = ["failure_note"]

_SYSTEM_ZH = (
    "你是调度平台值班工程师。根据给定的失败归因 JSON（失败总数、归因"
    "分布、同根因聚类：成员任务/错误样例/重试判定），起草一条发到值班群"
    "的失败通报：几个根因、各打挂了谁、哪些重试能救哪些不能、第一动作"
    "是什么。只输出通报正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the scheduler on-call. From the given failure-attribution "
    "JSON (total failures, cause distribution, root-cause clusters with "
    "member tasks, sample errors and retry verdicts), draft an "
    "ops-channel note: how many root causes, who each broke, which "
    "retries help and which are futile, and the first action. Markdown "
    "body only, terse.")


def failure_note(result: FailureResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready failure note for this attribution."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("task_failure", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
