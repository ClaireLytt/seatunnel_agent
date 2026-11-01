"""Chat/MCP tool entry point for the schema-to-DDL converter.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def avro2ddl(schema: str, table: str = "", dialect: str = "hive",
             lang: str = "") -> str:
    """消息 Schema 建表（确定性）：粘贴 Avro record 或 JSON Schema,生成
    Hive/Doris CREATE TABLE——logicalType 优先映射（decimal/date/
    timestamp）,[null,T] 解包为可空,多类型 union 落 STRING 并点名,Hive
    出真 ARRAY/MAP/STRUCT,Doris 复杂类型落 JSON 并给 key/分桶桩,doc 转
    COMMENT。DDL 经解析器回检同列数。不连注册中心与数据库。"""
    from seatunnel_agent.agents.data.avro2ddl import (
        convert_schema,
        render_markdown,
    )

    if not (schema or "").strip():
        return "Schema 不能为空 / the schema must not be empty"
    try:
        draft = convert_schema(schema, table=table, dialect=dialect)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(draft, lang=normalize_lang(lang))
