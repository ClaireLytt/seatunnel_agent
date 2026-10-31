"""Optional LLM drift note from a config diff.

The deterministic differ lists the differences; this layer turns them
into a paste-ready release-review note.  Strictly opt-in and bounded to
one call per diff.
"""

from __future__ import annotations

import json

from .differ import ConfigDiffResult

__all__ = ["drift_note"]

_SYSTEM_ZH = (
    "你是发布评审人。根据给定的配置漂移 JSON（按风险排序的差异：改值/"
    "新增/删除,高风险=吞吐/状态/数据去向类键,密钥已脱敏），起草一条"
    "发给发布群的评审意见：哪些差异是环境应有的（如 URL/表名指向各自"
    "环境）、哪些可疑需要确认（如并行度/checkpoint 改动）、放行还是"
    "打回。只输出意见正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the release reviewer. From the given config-drift JSON "
    "(differences ranked by risk — changed/added/removed, high = "
    "throughput/state/destination keys, secrets masked), draft a "
    "release-channel review: which differences are expected environment "
    "pointers (URLs, table names), which are suspicious and need "
    "confirmation (parallelism, checkpoint), and approve or bounce. "
    "Markdown body only, terse.")


def drift_note(result: ConfigDiffResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready drift review for this diff."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("config_diff", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
