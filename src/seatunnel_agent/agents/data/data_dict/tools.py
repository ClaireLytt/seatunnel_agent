"""Chat/MCP tool entry point for the data-dictionary generator.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def data_dict(catalog: str, sql: str = "", lang: str = "") -> str:
    """数据字典自动生成（确定性骨架）：粘贴资产目录（JSON 清单或建表
    DDL），可选再贴一份 SQL 负载；逐表输出字典骨架 — 每列的推断角色
    （键/时间/度量/标志/维度，按命名形态）、已有注释、SQL 使用频次
    （过滤/关联/分组出现次数）与各表注释覆盖率；空注释即待补清单。
    不连数据库。"""
    from seatunnel_agent.agents.data.data_dict import (
        generate_dict,
        render_markdown,
    )

    if not (catalog or "").strip():
        return "资产目录不能为空 / catalog must not be empty"
    try:
        result = generate_dict(catalog, sql_text=sql)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    except Exception as exc:  # malformed JSON/DDL
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
