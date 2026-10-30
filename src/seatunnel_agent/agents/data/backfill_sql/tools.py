"""Chat/MCP tool entry point for the backfill SQL agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def backfill_sql(spec: str, lang: str = "") -> str:
    """补数 SQL 生成（确定性）：粘贴 JSON 规格（table、partition_col、
    start/end 业务日期、带 {date} 占位符的 source SELECT、mode:
    overwrite/delete_insert/merge、dialect: hive/spark/mysql/doris，
    merge 需 keys），按业务日期逐分区生成幂等、带分区边界的安全补数语句，
    附前置行数校验 SQL。不带 {date} 的全表读取会被拒绝，日期范围封顶
    366 天。SQL 只生成，不执行。"""
    from seatunnel_agent.agents.data.backfill_sql import (
        generate,
        parse_spec,
        render_markdown,
    )

    if not (spec or "").strip():
        return "补数规格不能为空 / backfill spec must not be empty"
    try:
        result = generate(parse_spec(spec))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # json errors etc.
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
