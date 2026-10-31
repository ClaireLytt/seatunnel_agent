"""Chat/MCP tool entry point for the schema aligner.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def schema_align(source: str, sink: str, lang: str = "") -> str:
    """源目 Schema 对齐（确定性）：粘贴源表与目标表两份建表 DDL
    （MySQL/Hive/Doris 写法均可），按列名匹配后判定映射风险 — 目标端
    缺列（悄悄丢数）、多出的无默认 NOT NULL 列（写入必败）、类型收窄
    （bigint→int/decimal 降精度/varchar 截断）、危险转换（string→
    数值/时间）、时间截断（timestamp→date）、可空→NOT NULL;放宽类
    转换安全不报。同步作业上线前的一贴体检。不连数据库。"""
    from seatunnel_agent.agents.data.schema_align import (
        align_schemas,
        render_markdown,
    )

    if not (source or "").strip() or not (sink or "").strip():
        return "需要源目两份 DDL / both DDLs are required"
    try:
        result = align_schemas(source, sink)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
