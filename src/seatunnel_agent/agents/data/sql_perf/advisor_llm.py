"""Optional LLM SQL rewrite driven by the plan findings.

The deterministic analyzer says what the engine planned badly; given
the original SQL this layer drafts the rewrite that fixes the flagged
findings (add the partition predicate, unwrap the cast that blocked
pushdown, hint the broadcast, prune the projection).  Strictly opt-in,
one bounded call.
"""

from __future__ import annotations

from .analyzer import PlanReport

__all__ = ["rewrite_sql"]

_MAX_CHARS = 6_000

_SYSTEM_ZH = (
    "你是 SQL 性能优化专家。给定执行计划分析的发现（JSON）与原 SQL，"
    "输出改写后的 SQL：逐条针对发现（补分区谓词、把挡住下推的函数/转型"
    "挪走、广播 hint、裁剪投影列），并在 SQL 前用注释标注每处改动对应"
    "哪个发现编号。只输出一个 ```sql 代码块，不要解释。")
_SYSTEM_EN = (
    "You are a SQL performance expert. Given the plan-analysis findings "
    "(JSON) and the original SQL, output the rewritten SQL that fixes "
    "each finding (partition predicate, move the pushdown-blocking "
    "cast/function, broadcast hint, prune the projection), with a "
    "comment per change naming the finding code. Output a single "
    "```sql block only, no commentary.")


def rewrite_sql(report: PlanReport, sql: str, lang: str = "zh") -> str:
    """One LLM call → the optimized-SQL draft for the flagged findings."""
    import json

    from seatunnel_agent.common.llm import one_shot
    from seatunnel_agent.common.utils import truncate

    payload = (f"findings:\n"
               f"{json.dumps([f.to_dict() for f in report.findings], ensure_ascii=False)}\n\n"
               f"original SQL:\n```sql\n{truncate(sql, _MAX_CHARS)}\n```")
    return one_shot("sql_perf", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
