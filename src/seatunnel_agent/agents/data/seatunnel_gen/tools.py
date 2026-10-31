"""Chat/MCP tool entry point for the SeaTunnel job drafter.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def seatunnel_gen(ddl: str, source: str, sink: str, job_mode: str = "",
                  lang: str = "") -> str:
    """SeaTunnel 作业配置生成（确定性）：粘贴表的 CREATE TABLE DDL + 源/
    目标连接器名（如 MySQL-CDC → Doris）,生成完整 env/source/sink HOCON
    草稿——库/表/topic 参数按表名智能填充,其余必填参数带文档示例并列为
    待替换项;CDC 源自动 STREAMING。草稿经配置体检（config_lint）零错误
    回检。不连数据库。"""
    from seatunnel_agent.agents.data.seatunnel_gen import (
        generate_config,
        render_markdown,
    )

    if not (ddl or "").strip():
        return "DDL 不能为空 / DDL must not be empty"
    if not (source or "").strip() or not (sink or "").strip():
        return "源与目标连接器都要填 / both connectors are required"
    try:
        draft = generate_config(ddl, source, sink, job_mode=job_mode)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(draft, lang=normalize_lang(lang))
