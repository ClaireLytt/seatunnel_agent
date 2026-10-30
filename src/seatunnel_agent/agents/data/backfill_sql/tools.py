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


def backfill_specs(plan: str, partition_col: str = "dt",
                   dialect: str = "hive", lang: str = "") -> str:
    """补数规格桥接（确定性）：粘贴分区补数计划器（backfill_plan）输出的
    计划 JSON，为每张受影响的表生成一份可直接编辑的补数 SQL 规格骨架 —
    缺失/级联日期原样带入 dates 列表，source SELECT 留出带 {date} 边界的
    模板待填。改好后喂给 backfill_sql 即得逐分区幂等语句。不连数据库。"""
    import json as _json

    from seatunnel_agent.agents.data.backfill_sql.bridge import (
        specs_from_plan,
    )

    if not (plan or "").strip():
        return "计划 JSON 不能为空 / plan JSON must not be empty"
    try:
        specs = specs_from_plan(plan, partition_col=partition_col,
                                dialect=dialect)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # json errors etc.
        return f"输入有误 / bad input: {exc}"
    zh = normalize_lang(lang) == "zh"
    title = ("## 补数规格骨架（逐表，填好 source 后交给 backfill_sql）"
             if zh else
             "## Backfill spec skeletons (per table — fill in the "
             "source, then feed each to backfill_sql)")
    lines = [title, ""]
    for spec in specs:
        lines.append(f"**`{spec['table']}`** — {len(spec['dates'])} "
                     + ("个分区" if zh else "slot(s)"))
        lines.append("```json")
        lines.append(_json.dumps(spec, ensure_ascii=False, indent=2))
        lines.append("```")
    return "\n".join(lines)
