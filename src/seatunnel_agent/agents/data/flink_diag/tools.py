"""Chat/MCP tool entry point for the Flink diagnoser.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def flink_diag(snapshot: str, lang: str = "") -> str:
    """Flink 作业诊断（确定性）：粘贴作业快照 JSON（checkpoints[] 的
    duration/alignment/failed、operators[] 的 backpressure/watermark_
    lag_ms、restarts，各节可选），按严重度输出 — checkpoint 失败、时长
    暴涨（60/300s 或 2 倍中位数）、对齐耗时主导（建议 unaligned）、
    背压算子（0.5/0.8）、watermark 滞后（60/300s）、频繁重启（1/3 次
    每小时），每条附处方（指向 kafkalag/skew-runtime）。不连集群。"""
    from seatunnel_agent.agents.data.flink_diag import (
        diagnose_job,
        parse_job_snapshot,
        render_markdown,
    )

    if not (snapshot or "").strip():
        return "快照不能为空 / snapshot must not be empty"
    try:
        diag = diagnose_job(parse_job_snapshot(snapshot))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(diag, lang=normalize_lang(lang))
