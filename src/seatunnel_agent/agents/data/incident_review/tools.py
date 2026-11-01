"""Chat/MCP tool entry point for the incident reviewer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def incident_review(events: str, lang: str = "") -> str:
    """事故复盘（确定性）：粘贴事故事件日志（CSV 带表头或 JSONL,列 time/
    kind/text,kind 取 impact|alert|action|comm|recovery）,按时间线算出
    发现用时（影响→首个告警）、响应用时（告警→首个处置）、恢复用时
    （影响→最后恢复）,静默窗口与缺恢复事件分级点名。复盘里的数字不再靠
    回忆。不连监控系统。"""
    from seatunnel_agent.agents.data.incident_review import (
        render_markdown,
        review_incident,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    if not (events or "").strip():
        return "事件日志不能为空 / the event log must not be empty"
    try:
        headers, rows = parse_rows(events)
        review = review_incident(headers, rows)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(review, lang=normalize_lang(lang))
