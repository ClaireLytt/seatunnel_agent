"""Chat/MCP tool entry point for the task-failure classifier.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def task_failure(export: str, lang: str = "") -> str:
    """任务失败归因（确定性）：粘贴调度器失败任务导出（CSV 带表头或
    JSON 列表：task、可选 dag/error/retries/final_status），按错误文本
    归类（依赖缺失/资源/超时/连接/数据异常/代码错误），按归一化错误签名
    聚成同根因组（附成员、错误样例），判定重试有效性（瞬态/无效/部分），
    每类附处方（指向 backfill/dagconflict/slowquery/datarepair）。
    不连调度器。"""
    from seatunnel_agent.agents.data.task_failure import (
        classify_failures,
        parse_failures,
        render_markdown,
    )

    if not (export or "").strip():
        return "导出不能为空 / export must not be empty"
    try:
        result = classify_failures(parse_failures(export))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
