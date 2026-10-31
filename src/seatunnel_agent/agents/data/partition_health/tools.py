"""Chat/MCP tool entry point for the partition-health analyzer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def partition_health(listing: str, lang: str = "") -> str:
    """分区健康体检（确定性）：粘贴分区清单（CSV 带表头或 JSON 列表：
    table/partition/size_gb/可选 rows），逐表输出 — 日期断档（回刷洞）、
    空分区（跑了没写）、大小倾斜（5/20 倍表中位数）、最新分区暴涨
    （3/10 倍）或缩水（<0.3 倍），每条附处方（指向 backfill/dupcheck/
    datavolatility）。按不按时到是 data_freshness 的事。不连数据库。"""
    from seatunnel_agent.agents.data.partition_health import (
        analyze_partitions,
        parse_partition_listing,
        render_markdown,
    )

    if not (listing or "").strip():
        return "清单不能为空 / listing must not be empty"
    try:
        result = analyze_partitions(parse_partition_listing(listing))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
