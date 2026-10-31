"""Chat/MCP tool entry point for the capacity forecaster.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def capacity_forecast(series: str, quota: float, window: int = 14,
                      lang: str = "") -> str:
    """容量耗尽预测（确定性）：粘贴存储时间序列（CSV 表头 date,metric,
    value 或同字段 JSONL,metric=表名,value=GB 或行数,多表共用一份;
    名为 total 的指标直接作为总量）+ 配额;最近 window 个点做最小二乘
    斜率、线性外推 → 预计耗尽日期（90/30 天视界告警）、增长大户排行
    （含增速占比）与在缩小的指标。阶跃变化会使日期失效。不连存储。"""
    from seatunnel_agent.agents.data.capacity_forecast import (
        forecast_capacity,
        render_markdown,
    )

    if not (series or "").strip():
        return "序列不能为空 / series must not be empty"
    try:
        result = forecast_capacity(series, quota=quota, window=window)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
