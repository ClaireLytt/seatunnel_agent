"""Chat/MCP tool entry point for the database diagnoser.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def db_diag(snapshot: str, lang: str = "") -> str:
    """数据库运行诊断（确定性）：粘贴状态快照 JSON（variables.max_
    connections、status.threads_connected/threads_running/cpu_pct、
    lock_waits、deadlocks、slow_queries，各节均可选），按严重度输出 —
    连接池吃紧（80/95%）、执行线程风暴（32/128）、长锁等待（5/30s，
    附最严重阻塞对）、死锁、慢查询热点（>1s）、CPU 饱和（80/95%），
    每条附处方。不连库。"""
    from seatunnel_agent.agents.data.db_diag import (
        diagnose_snapshot,
        parse_snapshot,
        render_markdown,
    )

    if not (snapshot or "").strip():
        return "快照不能为空 / snapshot must not be empty"
    try:
        diag = diagnose_snapshot(parse_snapshot(snapshot))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(diag, lang=normalize_lang(lang))
