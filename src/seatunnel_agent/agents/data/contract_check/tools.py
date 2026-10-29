"""Chat/MCP tool entry point for the data-contract agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations


def _lang(lang: str) -> str:
    return "en" if (lang or "zh").strip().lower().startswith("en") else "zh"


def contract_check(sql: str, contract: str, dialect: str = "hive",
                   lang: str = "") -> str:
    """数据契约校验（确定性）：拿 YAML 契约（tables: 声明列/类型/注释
    要求/分区键）对照实际 DDL，逐条报出 表缺失/列缺失/类型违约/分区
    违约/缺注释/契约外列，按严重度分级。不连库不执行。"""
    from seatunnel_agent.agents.data.contract_check import (
        check_sql_text,
        render_markdown,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    if not (contract or "").strip():
        return "契约不能为空 / contract must not be empty"
    try:
        report = check_sql_text(sql, dialect=dialect, contract=contract)
    except ValueError as exc:
        return f"契约格式错误 / bad contract: {exc}"
    except Exception as exc:
        return f"校验失败 / check failed: {exc}"
    return render_markdown(report, lang=_lang(lang))
