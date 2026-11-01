"""Chat/MCP tool entry point for the alert-storm analyzer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def alert_storm(export: str, lang: str = "") -> str:
    """告警风暴聚合（确定性）：粘贴告警导出（CSV 带表头或 JSON 列表：
    ts/source/title/level），按归一化标题签名聚类（同根因 N 条合 1,
    给出降噪倍数），并检出风暴窗口（5 分钟桶超中位数 3 倍）、反复横跳
    签名（一小时内 5+ 次,抑制窗口候选）与吵闹来源（占比 ≥50%），每条
    附处方。不连告警系统。"""
    from seatunnel_agent.agents.data.alert_storm import (
        analyze_alerts,
        parse_alerts,
        render_markdown,
    )

    if not (export or "").strip():
        return "导出不能为空 / export must not be empty"
    try:
        result = analyze_alerts(parse_alerts(export))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
