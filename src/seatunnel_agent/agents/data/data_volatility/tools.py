"""Chat/MCP tool entry point for the data-volatility analyzer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def data_volatility(series: str, lang: str = "") -> str:
    """数据波动分析（确定性）：粘贴指标时间序列（CSV 表头 date,metric,
    value 或同字段 JSONL，多指标共用一份），按严重度输出波动发现 —
    突增/突降（7 点滚动中位数 + MAD，附日期与幅度）、水平位移（近期 vs
    此前中位数 ±30/60%）、走平（历史在动、近期冻结）、日期断档。处方
    指向质量根因追踪。不连数据库。"""
    from seatunnel_agent.agents.data.data_volatility import (
        analyze_series,
        parse_series,
        render_markdown,
    )

    if not (series or "").strip():
        return "序列不能为空 / series must not be empty"
    try:
        result = analyze_series(parse_series(series))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
