"""Chat/MCP tool entry point for the timezone auditor.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def timezone_audit(data: str, lang: str = "") -> str:
    """时间戳体检（确定性）：粘贴含时间戳列的数据行（CSV 带表头或 JSONL）,
    逐列审计语义——同列显式时区不一致（+08:00 混 Z,直接证据）、epoch 秒/
    毫秒混用（聚合差千倍）、小时分布 8 小时双峰（UTC/本地混用嫌疑,启发
    式）、1980..2100 之外的哨兵值。不连数据库。"""
    from seatunnel_agent.agents.data.sample_profile import parse_rows
    from seatunnel_agent.agents.data.timezone_audit import (
        audit_timezones,
        render_markdown,
    )

    if not (data or "").strip():
        return "数据不能为空 / data must not be empty"
    try:
        headers, rows = parse_rows(data)
        audit = audit_timezones(headers, rows)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(audit, lang=normalize_lang(lang))
