"""Optional LLM source-SELECT fill for backfill spec skeletons.

The planner bridge emits specs whose source SELECT is a bounded
template with the columns left to fill; given the upstream DDL this
layer fills them in.  Safety stays deterministic: a reply without the
``{date}`` placeholder is rejected and the skeleton kept, so the
no-unbounded-reads rule cannot be talked out of.
"""

from __future__ import annotations

from typing import Any

__all__ = ["fill_source", "fill_specs"]

_MAX_DDL_CHARS = 6_000

_SYSTEM_ZH = (
    "你是数据仓库工程师。给定补数目标表的规格 JSON 与上游表的 CREATE "
    "TABLE DDL，写出补数用的 source SELECT：显式列清单（不要 SELECT *），"
    "分区过滤必须保留 {date} 占位符原样出现。只输出一条 SQL 语句本身，"
    "不要代码块围栏、不要解释。")
_SYSTEM_EN = (
    "You are a data-warehouse engineer. Given the backfill spec JSON and "
    "the upstream CREATE TABLE DDL, write the source SELECT: explicit "
    "column list (no SELECT *), and the partition filter must keep the "
    "literal {date} placeholder. Output the single SQL statement only — "
    "no code fences, no commentary.")


def fill_source(spec: dict[str, Any], ddl: str, lang: str = "zh") -> str:
    """One LLM call → the filled source SELECT (or raise on bad input)."""
    import json

    from seatunnel_agent.common.llm import one_shot

    prompt = (f"spec:\n{json.dumps(spec, ensure_ascii=False)}\n\n"
              f"upstream DDL:\n```sql\n{ddl[:_MAX_DDL_CHARS]}\n```")
    reply = one_shot("backfill_sql", _SYSTEM_ZH, _SYSTEM_EN, prompt, lang)
    return reply.strip("`").strip().rstrip(";")


def fill_specs(specs: list[dict[str, Any]], ddl: str,
               lang: str = "zh") -> list[str]:
    """Fill every spec's source in place; returns per-spec warnings.

    A reply that drops the ``{date}`` placeholder is discarded — the
    skeleton stays and the violation is reported instead of trusted.
    """
    warnings: list[str] = []
    for spec in specs:
        filled = fill_source(spec, ddl, lang=lang)
        if "{date}" in filled:
            spec["source"] = filled
        else:
            warnings.append(
                f"{spec['table']}: LLM reply lost the {{date}} placeholder "
                f"— skeleton kept")
    return warnings
