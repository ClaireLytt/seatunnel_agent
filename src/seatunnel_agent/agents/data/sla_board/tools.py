"""Chat/MCP tool entry point for the SLA board.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def sla_board(records: str, target: float = 0.95, lang: str = "") -> str:
    """SLA 达成看板（确定性）：粘贴任务完成记录（CSV 带表头或 JSONL,列
    task/date/deadline/finish,时间 HH:MM 过午夜可写 25:30 或 ISO）,
    逐任务给出达成率、迟到 p50/p90/最差、连续破线天数,低于目标/连续
    失守/慢性迟到分级点名。不连调度器。"""
    from seatunnel_agent.agents.data.sample_profile import parse_rows
    from seatunnel_agent.agents.data.sla_board import (
        build_board,
        render_markdown,
    )

    if not (records or "").strip():
        return "记录不能为空 / records must not be empty"
    try:
        headers, rows = parse_rows(records)
        board = build_board(headers, rows, target=target)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(board, lang=normalize_lang(lang))
