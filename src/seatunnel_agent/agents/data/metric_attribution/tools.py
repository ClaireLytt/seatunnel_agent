"""Chat/MCP tool entry point for the metric attributor.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def metric_attribution(baseline: str, current: str, dims: str,
                       metric: str, lang: str = "") -> str:
    """指标异动归因（确定性）："昨天 GMV 为什么跌、哪个渠道贡献的"。
    粘贴基线与当前两份按维度切分的结果集（CSV 带表头或 JSONL）+ 维度列
    （逗号分隔）+ 指标列;按维度精确可加分解逐值贡献额与占比（含新出现/
    消失的值），并判定头号贡献、高度集中（单点事故）与结构漂移（涨跌
    对冲）。不连数据库。"""
    from seatunnel_agent.agents.data.metric_attribution import (
        attribute_change,
        render_markdown,
    )

    if not (baseline or "").strip() or not (current or "").strip():
        return "需要基线与当前两份结果 / both result sets are required"
    try:
        result = attribute_change(baseline, current, dims, metric)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
