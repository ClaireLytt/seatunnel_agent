"""Chat/MCP tool entry point for the grant reviewer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def grant_review(application: str, lang: str = "") -> str:
    """数据权限申请审核（确定性）：粘贴申请单 JSON（applicant/role/
    purpose/tables[{table,columns}]/duration_days/write，支持单份或
    列表），按内置敏感级词表（S3 直接标识与资金、S2 准标识）透明打分 —
    整表 +20、非写角色要写 +30、超期 +8/15、用途过短 +15；70 分拒绝、
    40 分降级批准并给出具体降级建议（脱敏/按列/只读/压期限）。不连库。"""
    from seatunnel_agent.agents.data.grant_review import (
        parse_applications,
        render_markdown,
        review_grants,
    )

    if not (application or "").strip():
        return "申请单不能为空 / application must not be empty"
    try:
        result = review_grants(parse_applications(application))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
