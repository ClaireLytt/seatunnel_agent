"""Optional LLM migration review from an evolve plan.

The deterministic evolver writes the statements; this layer drafts the
rollout advice — ordering, timing, consumer notice.  Strictly opt-in
and bounded to one call per plan.
"""

from __future__ import annotations

import json

from .evolver import EvolvePlan

__all__ = ["migration_note"]

_SYSTEM_ZH = (
    "你是数仓变更评审。给定一份 DDL 迁移计划 JSON（可执行步骤与被注释的"
    "危险步骤：删表删列、类型收窄、分区变更），起草执行建议：步骤先后、"
    "危险项各自该走什么替代路径（归档/新列回填/建新表换名）、要先通知"
    "哪些下游。只输出建议 markdown，按执行顺序排列，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are a warehouse change reviewer. Given a DDL migration plan "
    "JSON (runnable steps plus commented dangerous ones: drops, "
    "narrowings, partition changes), draft the rollout advice: step "
    "ordering, the safer path for each dangerous item (archive, "
    "backfill a new column, build-and-swap), and which consumers to "
    "notify first. Markdown only, in execution order, terse.")


def migration_note(plan: EvolvePlan, lang: str = "zh") -> str:
    """One LLM call → rollout advice for this migration."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(plan.to_dict(), ensure_ascii=False)
    return one_shot("ddl_evolve", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
