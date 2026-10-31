"""Chat/MCP tool entry point for the realtime-offline reconciler.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def rt_offline_diff(realtime: str, offline: str, keys: str,
                    tolerance_pct: float = 1.0, lang: str = "") -> str:
    """实时与离线数据核对（确定性）：粘贴实时与离线两份结果集（CSV 带
    表头或 JSONL）+ 键列（逗号分隔）+ 相对容差%；按键对齐后输出 — 双侧
    缺失键、超容差的单元格差异（差距大在前）、系统性偏差判定（实时普遍
    偏低 → 迟到/窗口未闭；普遍偏高 → 重复消费）与一致率。连库 checksum
    比对请用 data_comparison。"""
    from seatunnel_agent.agents.data.rt_offline_diff import (
        compare_results,
        render_markdown,
    )

    if not (realtime or "").strip() or not (offline or "").strip():
        return "需要实时与离线两份结果 / both result sets are required"
    try:
        result = compare_results(realtime, offline, keys,
                                 tolerance_pct=tolerance_pct)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
