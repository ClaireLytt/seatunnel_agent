"""Chat/MCP tool entry point for the slow-query diagnoser.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def slow_query(metrics: str, baseline: str = "", lang: str = "") -> str:
    """慢查询根因分析（确定性）：粘贴一次执行的指标 JSON（duration_s、
    scan_bytes、gc_s、queue_s、stages 里每个 stage 的 task_max_s/
    task_median_s/spill_bytes/input_bytes/tasks），可选历史基线 jsonl
    （每行一次历史运行）。规则定位并按占比排序：倾斜、扫描暴涨、溢写、
    GC 压力、排队、小文件 — 每条附证据与指向对应 agent 的处方。不连集群。"""
    from seatunnel_agent.agents.data.slow_query import (
        diagnose,
        parse_baseline,
        parse_metrics,
        render_markdown,
    )

    if not (metrics or "").strip():
        return "执行指标不能为空 / run metrics must not be empty"
    try:
        diag = diagnose(parse_metrics(metrics),
                        parse_baseline(baseline))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(diag, lang=normalize_lang(lang))
