"""Chat/MCP tool entry point for the compaction planner.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def compact_plan(inventory: str, small_mb: float = 32.0,
                 target_mb: float = 256.0, lang: str = "") -> str:
    """小文件治理（确定性）：粘贴文件清单（CSV 带表头或 JSONL,列 table/
    partition/file_count/total_mb）,找出小文件分区（均值低于阈值且文件
    数 >10,小而少不动）,按收敛文件数排名合并候选并给 CONCATENATE /
    INSERT OVERWRITE 模板;千文件级极端分区与表级占比分级点名。
    partition_health 管分区大小,本工具管分区里的文件数。不连集群。"""
    from seatunnel_agent.agents.data.compact_plan import (
        plan_compaction,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    if not (inventory or "").strip():
        return "清单不能为空 / inventory must not be empty"
    try:
        headers, rows = parse_rows(inventory)
        plan = plan_compaction(headers, rows, small_mb=small_mb,
                               target_mb=target_mb)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(plan, lang=normalize_lang(lang))
