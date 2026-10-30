"""Chat/MCP tool entry point for the metadata-quality agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def metadata_quality(sql: str, dialect: str = "hive", lang: str = "") -> str:
    """元数据质量体检（确定性）：对 DDL 做规约检查——列注释
    覆盖率、分层命名错配（如 dwd 库里的 ods_ 表）、金额列用浮点/
    日期列用裸 STRING 等类型反模式，按严重度分级。"""
    from seatunnel_agent.agents.data.metadata_quality import (
        check_sql_text,
        render_markdown,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    try:
        report = check_sql_text(sql, dialect=dialect)
    except Exception as exc:
        return f"检查失败 / check failed: {exc}"
    return render_markdown(report, lang=normalize_lang(lang))
