"""Chat/MCP tool entry point for the duplicate checker.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def dup_check(data: str, pk: str = "", biz_key: str = "",
              lang: str = "") -> str:
    """数据重复检测（确定性）：粘贴 CSV（带表头）或 JSONL 数据行，可选
    声明主键列与业务键列（逗号分隔），三层检测重复 — 全行重复、主键重复、
    业务事件重复；每组给出行数、首末行号与差异列（差异列指向重复来源：
    重跑/上游多路写入/缺少去重窗口）。不连数据库。"""
    from seatunnel_agent.agents.data.dup_check import (
        detect_dups,
        render_markdown,
    )

    if not (data or "").strip():
        return "数据不能为空 / data must not be empty"
    try:
        result = detect_dups(data, pk=pk or None, biz_key=biz_key or None)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
