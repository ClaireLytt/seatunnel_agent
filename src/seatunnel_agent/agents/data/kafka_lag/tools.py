"""Chat/MCP tool entry point for the Kafka-lag analyzer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def kafka_lag(snapshot: str, lang: str = "") -> str:
    """Kafka 消费积压诊断（确定性）：粘贴消费组 offset 快照（JSON 的
    topics[].partitions[]：log_end_offset/committed_offset/consume_rate/
    produce_rate，或同字段 CSV），按严重度输出 — 积压量级（10 万/100
    万）、热点分区（5/20 倍中位数）、消费追不上生产（含永不追上判定）、
    停滞分区（速率 0 且有 lag）、追赶 ETA（30/180 分钟），每条附处方，
    另附积压 Top 分区表。不连 broker。"""
    from seatunnel_agent.agents.data.kafka_lag import (
        analyze_lag,
        parse_lag_snapshot,
        render_markdown,
    )

    if not (snapshot or "").strip():
        return "快照不能为空 / snapshot must not be empty"
    try:
        group, parts = parse_lag_snapshot(snapshot)
        result = analyze_lag(group, parts)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed JSON/CSV
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
