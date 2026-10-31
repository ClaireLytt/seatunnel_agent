"""Chat/MCP tool entry point for the DAG conflict detector.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def dag_conflict(scenario: str, lang: str = "") -> str:
    """并发任务冲突检测（确定性）：粘贴场景 JSON — capacity（slots/
    memory_gb）与多个 dags（name、start 启动偏移、tasks 含 deps/duration/
    slots/memory_gb/writes）。各 DAG 按依赖 ASAP 推演时间线，找出资源
    超容的时间窗与窗内任务、跨 DAG 写同一张表的写写冲突，并给出经重新
    模拟验证的错峰建议（顺延哪个 DAG 多久、峰值降到多少）。不连调度器。"""
    from seatunnel_agent.agents.data.dag_conflict import (
        parse_scenario,
        render_markdown,
        simulate,
    )

    if not (scenario or "").strip():
        return "场景 JSON 不能为空 / scenario JSON must not be empty"
    try:
        report = simulate(parse_scenario(scenario))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(report, lang=normalize_lang(lang))
