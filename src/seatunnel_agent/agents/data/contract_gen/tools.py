"""Chat/MCP tool entry point for the contract generator.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def contract_gen(sql: str, tables: str = "", with_types: bool = True,
                 strict: bool = False, lang: str = "") -> str:
    """数据契约草稿生成（确定性）：粘贴 CREATE TABLE DDL，按表当前已做到的
    承诺（列与类型、分区布局、注释纪律）生成契约体检可直接消费的
    contract YAML 草稿。tables 可逗号分隔限定表;strict=true 时
    allow_extra_columns: false。草稿已通过契约体检解析器回检。"""
    from seatunnel_agent.agents.data.contract_gen import (
        generate_contract,
        render_markdown,
    )

    if not (sql or "").strip():
        return "DDL 不能为空 / DDL must not be empty"
    wanted = [t.strip() for t in (tables or "").split(",") if t.strip()]
    try:
        draft = generate_contract(sql, with_types=with_types,
                                  allow_extra=not strict,
                                  tables=wanted or None)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(draft, lang=normalize_lang(lang))
