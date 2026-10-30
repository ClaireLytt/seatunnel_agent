"""Chat/MCP tool entry point for the migration-guard agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations


def _lang(lang: str) -> str:
    return "en" if (lang or "zh").strip().lower().startswith("en") else "zh"


def ddl_guard(sql: str, dialect: str = "hive", lang: str = "") -> str:
    """迁移守卫（确定性，不连库不执行）：对上线迁移脚本(ALTER/DROP/
    RENAME 流)分级报出危险操作——删表/删列/清空/类型收窄 high,重命名/
    类型变更/NOT NULL 无默认值 medium——并生成逆序回滚脚本,不可逆步骤
    显式标注。"""
    from seatunnel_agent.agents.data.ddl_guard import (
        render_markdown,
        scan_sql_text,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    try:
        report = scan_sql_text(sql, dialect=dialect)
    except Exception as exc:
        return f"扫描失败 / scan failed: {exc}"
    return render_markdown(report, lang=_lang(lang))
