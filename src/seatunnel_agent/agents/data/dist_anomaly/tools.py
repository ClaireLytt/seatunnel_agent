"""Chat/MCP tool entry point for the distribution-anomaly comparator.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def dist_anomaly(baseline: str, current: str, max_rows: int = 2000,
                 lang: str = "") -> str:
    """数据分布异常检测（确定性）：粘贴基线与当前两份数据样本（CSV 带
    表头 / JSONL / sampleprofile 的 profile JSON），逐列对比并按严重度
    输出漂移发现 — schema 增删列、均值漂移（±20/50%）、空值率与唯一率
    突变（±10/25pp）、类别占比漂移（L1 0.2/0.4，附移动最大的类别）、
    新增/消失类别、主类型变化。不连数据库。"""
    from seatunnel_agent.agents.data.dist_anomaly import (
        compare_profiles,
        load_profile,
        render_markdown,
    )

    if not (baseline or "").strip() or not (current or "").strip():
        return "需要基线与当前两份样本 / both baseline and current are required"
    try:
        result = compare_profiles(load_profile(baseline, max_rows),
                                  load_profile(current, max_rows))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
