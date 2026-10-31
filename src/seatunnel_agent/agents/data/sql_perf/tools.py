"""Chat/MCP tool entry point for the execution-plan analyzer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def sql_perf(plan: str, lang: str = "") -> str:
    """执行计划分析（确定性）：粘贴 EXPLAIN / EXPLAIN FORMATTED 的输出
    （Spark 或 Hive），解析 join 类型、Exchange/shuffle、各表扫描的
    PartitionFilters 与 PushedFilters，按级别给出发现与处方：笛卡尔积、
    全分区扫描、谓词未下推、多余 shuffle、可广播的 SortMergeJoin、
    宽表扫描。只读计划文本，不连引擎。"""
    from seatunnel_agent.agents.data.sql_perf import analyze, render_markdown

    if not (plan or "").strip():
        return "计划文本不能为空 / plan text must not be empty"
    try:
        report = analyze(plan)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(report, lang=normalize_lang(lang))
