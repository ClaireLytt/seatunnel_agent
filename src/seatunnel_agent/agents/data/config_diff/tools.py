"""Chat/MCP tool entry point for the config differ.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def config_diff(left: str, right: str, lang: str = "") -> str:
    """配置漂移对比（确定性）：粘贴两份作业配置（SeaTunnel HOCON/JSON/
    扁平 properties 均可,注释与顺序不计），语义化输出差异 — 改值/新增/
    删除,按风险分级（高=并行度/内存/checkpoint/表名/URL 等吞吐、状态、
    数据去向类键;中=batch/retry/timeout 等调优旋钮）;密钥形值脱敏但
    改动仍计。不连环境。"""
    from seatunnel_agent.agents.data.config_diff import (
        diff_configs,
        render_markdown,
    )

    if not (left or "").strip() or not (right or "").strip():
        return "需要左右两份配置 / both configs are required"
    try:
        result = diff_configs(left, right)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
