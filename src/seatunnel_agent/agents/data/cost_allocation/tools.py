"""Chat/MCP tool entry point for the cost allocator.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def cost_allocation(inventory: str, storage_price: float = 0.02,
                    compute_price: float = 0.5, lang: str = "") -> str:
    """成本分摊（确定性）：粘贴用量清单（CSV 带表头或 JSONL,列 owner/item/
    storage_gb/compute_hours,owner 为空计入无主）+ 存储/计算单价,逐归属方
    出账单与各家成本大头;无主开销占比与单家独大分级点名。同清单同单价
    必得同账单。不连计费系统。"""
    from seatunnel_agent.agents.data.cost_allocation import (
        allocate_costs,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    if not (inventory or "").strip():
        return "清单不能为空 / inventory must not be empty"
    try:
        headers, rows = parse_rows(inventory)
        bill = allocate_costs(headers, rows, storage_price=storage_price,
                              compute_price=compute_price)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(bill, lang=normalize_lang(lang))
