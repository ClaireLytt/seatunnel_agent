"""Chat/MCP tool entry point for the join auditor.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def join_audit(left: str, right: str, keys: str, lang: str = "") -> str:
    """关联质量审计（确定性）：粘贴两份数据行（CSV 带表头或 JSONL）+ 关联
    键（同名写 k,异名写 lk=rk,逗号组合多键）,审计 JOIN 本身——两侧匹配
    率、孤儿键、空键占比、多对多键导致的行数爆炸系数与最严重键。JOIN
    上线前最后一道检查。不连数据库。"""
    from seatunnel_agent.agents.data.join_audit import (
        audit_join,
        parse_keys,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    if not (left or "").strip() or not (right or "").strip():
        return "两侧数据都不能为空 / both sides are required"
    try:
        lh, lrows = parse_rows(left)
        rh, rrows = parse_rows(right)
        report = audit_join(lh, lrows, rh, rrows, parse_keys(keys))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(report, lang=normalize_lang(lang))
