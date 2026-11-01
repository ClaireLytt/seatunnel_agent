"""Chat/MCP tool entry point for the mask previewer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def mask_preview(data: str, preview_rows: int = 20, lang: str = "") -> str:
    """脱敏预览（确定性）：粘贴 CSV（带表头）或 JSONL 数据行，按列名
    （pii_scan 规则库）与值形态（手机号/身份证/邮箱/银行卡）识别敏感列,
    逐列做保格式值级脱敏（138****1234 等）,给出规则表 + 脱敏后样例。
    数据不出进程,不连数据库。"""
    from seatunnel_agent.agents.data.mask_preview import (
        preview_mask,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    if not (data or "").strip():
        return "数据不能为空 / data must not be empty"
    try:
        headers, rows = parse_rows(data)
        preview = preview_mask(headers, rows, preview_rows=preview_rows)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(preview, lang=normalize_lang(lang))
