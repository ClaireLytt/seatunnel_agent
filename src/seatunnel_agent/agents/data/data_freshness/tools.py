"""Chat/MCP tool entry point for the data freshness agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def data_freshness(events: str, rules: str = "", now: str = "",
                   lang: str = "") -> str:
    """数据新鲜度判定（确定性）：粘贴表更新事件清单（JSON 或 CSV，
    字段 table/updated），可选规则 JSON（表名通配 → interval/max_age），
    按规则或历史间隔中位数判定每张表：迟到 / 断更 / 过期 / 正常。
    now 默认取清单里最晚的更新时间，可覆盖。不连数据库。"""
    from seatunnel_agent.agents.data.data_freshness import (
        parse_events,
        parse_rules,
        render_markdown,
        scan,
    )

    if not (events or "").strip():
        return "更新事件不能为空 / update events must not be empty"
    try:
        result = scan(parse_events(events), parse_rules(rules),
                      now=now.strip() or None)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
