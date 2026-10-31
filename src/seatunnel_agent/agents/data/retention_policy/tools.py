"""Chat/MCP tool entry point for the retention advisor.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def retention_policy(inventory: str, active_days: int = 90,
                     lang: str = "") -> str:
    """生命周期建议（确定性）：粘贴分区清单（CSV 带表头或 JSONL,列 table/
    partition/size_gb/last_access,分区值 dt=YYYY-MM-DD 可解析）,逐表给出
    建议 TTL（仍有人读的最老分区年龄 + 30 天余量,按 30 天取整）、可归档
    分区与释放空间、从未被读的清理候选。基准日取数据内最新日期,同清单
    必得同建议。不连数据库。"""
    from seatunnel_agent.agents.data.retention_policy import (
        advise_retention,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    if not (inventory or "").strip():
        return "清单不能为空 / inventory must not be empty"
    try:
        headers, rows = parse_rows(inventory)
        report = advise_retention(headers, rows, active_days=active_days)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(report, lang=normalize_lang(lang))
