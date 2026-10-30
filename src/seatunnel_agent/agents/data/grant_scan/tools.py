"""Chat/MCP tool entry point for the grant-surface agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def grant_scan(sql: str, dialect: str = "hive", lang: str = "") -> str:
    """权限面扫描（确定性，不连库不执行）：解析脚本里的 GRANT/REVOKE,
    REVOKE 抵销后给出净授权面,并分级报出 公开授权(PUBLIC)/敏感表授权
    (同脚本 PII 命中表)/ALL 宽权限/库级宽范围。"""
    from seatunnel_agent.agents.data.grant_scan import (
        render_markdown,
        scan_sql_text,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    try:
        report = scan_sql_text(sql, dialect=dialect)
    except Exception as exc:
        return f"扫描失败 / scan failed: {exc}"
    return render_markdown(report, lang=normalize_lang(lang))
