"""Chat/MCP tool entry point for the CDC diagnoser.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def cdc_diag(snapshot: str, lang: str = "") -> str:
    """CDC 同步异常诊断（确定性）：粘贴同步快照 JSON（source 的 binlog_
    file/position/retention_hours、consumer 的 binlog_file/position/
    last_event_ts/now、可选 errors[]，各节可选），按严重度输出 —
    binlog 文件落后（1/3）、同文件字节落后（10/200MB）、事件停滞（5/30
    分钟）、保留期丢数风险（落后占窗口 50/80%）、错误分类（schema 变更/
    主键冲突/连接）、消费端超前源端（断点错乱），每条附处方。不连库。"""
    from seatunnel_agent.agents.data.cdc_diag import (
        diagnose_cdc,
        parse_cdc_snapshot,
        render_markdown,
    )

    if not (snapshot or "").strip():
        return "快照不能为空 / snapshot must not be empty"
    try:
        diag = diagnose_cdc(parse_cdc_snapshot(snapshot))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(diag, lang=normalize_lang(lang))
