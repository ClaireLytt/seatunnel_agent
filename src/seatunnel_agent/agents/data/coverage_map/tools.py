"""Chat/MCP tool entry point for the coverage mapper.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def coverage_map(ddl: str, rules: str = "", contract: str = "",
                 lang: str = "") -> str:
    """质量覆盖地图（确定性）：粘贴数仓 CREATE TABLE DDL + 已配置的 DQC
    规则 YAML 和/或契约 YAML,逐表标出有哪些闸（row_count/null_rate/
    unique/enum/契约）——裸奔的表分级点名（热层 dwd/dws/ads 记 high）,
    守着不存在表的死闸一并揪出,给总体覆盖率。不连数据库。"""
    from seatunnel_agent.agents.data.coverage_map import (
        map_coverage,
        render_markdown,
    )

    if not (ddl or "").strip():
        return "DDL 不能为空 / DDL must not be empty"
    try:
        cmap = map_coverage(ddl, rules_text=rules, contract_text=contract)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(cmap, lang=normalize_lang(lang))
