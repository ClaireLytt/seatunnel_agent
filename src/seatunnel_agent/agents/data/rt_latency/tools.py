"""Chat/MCP tool entry point for the realtime-latency analyzer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def rt_latency(events: str, sla_ms: float = 0, lang: str = "") -> str:
    """实时数据延迟分析（确定性）：粘贴事件时间戳行（CSV 带表头或
    JSONL：event_id + 各阶段 *_ts 列如 produce_ts/ingest_ts/process_ts/
    sink_ts，ISO 时间或毫秒时间戳，后段可缺省），输出各段与端到端的
    p50/p95/max、主导段（p95 时间花在哪）、离群事件（端到端 > 3 倍中位数，
    附最慢段）与可选 SLA 破线数。不连任何系统。"""
    from seatunnel_agent.agents.data.rt_latency import (
        analyze_latency,
        parse_events,
        render_markdown,
    )

    if not (events or "").strip():
        return "事件行不能为空 / events must not be empty"
    try:
        stages, evs = parse_events(events)
        result = analyze_latency(stages, evs, sla_ms=sla_ms)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
