"""Chat/MCP tool entry point for the DDL evolver.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def ddl_evolve(old_sql: str, new_sql: str, dialect: str = "hive",
               lang: str = "") -> str:
    """DDL 迁移脚本生成（确定性）：粘贴新旧两版 CREATE TABLE 快照,把差异
    （schema_drift 复用）直接变成迁移脚本——拓宽/加列/改名/改注释/新建表
    可直接执行;删表删列/类型收窄/分区变更只生成注释掉的语句并附评审
    提示,防误执行。支持 hive/mysql 拼写。不连数据库。"""
    from seatunnel_agent.agents.data.ddl_evolve import (
        build_migration,
        render_markdown,
    )

    if not (old_sql or "").strip() or not (new_sql or "").strip():
        return "两版 DDL 都不能为空 / both DDL snapshots are required"
    try:
        plan = build_migration(old_sql, new_sql, dialect=dialect)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(plan, lang=normalize_lang(lang))
