"""Chat/MCP tool entry point for the sample profiler.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def sample_profile(data: str, max_rows: int = 2000, lang: str = "") -> str:
    """数据抽样剖析（确定性）：粘贴 CSV（带表头）或 JSONL 数据行，等距
    抽样后逐列剖析 — 类型推断、空值率、唯一率、数值范围、高频值、格式桶
    （日期/邮箱/电话/UUID/整数/小数…），并按严重度列出异常发现：混合
    类型、高空值、常量列、离群格式（附行号）、数值存成文本、空白/大小写
    漂移。不连数据库。"""
    from seatunnel_agent.agents.data.sample_profile import (
        parse_rows,
        profile_rows,
        render_markdown,
        sample_rows,
    )

    if not (data or "").strip():
        return "数据不能为空 / data must not be empty"
    try:
        headers, rows = parse_rows(data)
        result = profile_rows(headers, sample_rows(rows, max_rows),
                              total_rows=len(rows))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed CSV/JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
