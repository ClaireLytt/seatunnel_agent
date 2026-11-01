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


def topic_onboard(schema: str, table: str = "", dialect: str = "hive",
                  source: str = "kafka", sink: str = "hive",
                  sample: str = "", lang: str = "") -> str:
    """Topic 接入三连（确定性）：粘贴 Avro record / JSON Schema,一次产出
    落地套件——avro2ddl 的 CREATE TABLE、seatunnel_gen 的同步作业 HOCON
    （已 lint,占位符点名）、contract_gen 的契约 YAML;再附样例数据（CSV
    带表头/JSONL）则同时生成 dq_rulegen 的 rules.yaml。每件产物由原生成
    器产出并各自回检。不连注册中心与数据库。"""
    from seatunnel_agent.agents.data.avro2ddl import (
        onboard_topic,
        render_onboard,
    )

    if not (schema or "").strip():
        return "Schema 不能为空 / the schema must not be empty"
    try:
        bundle = onboard_topic(schema, table=table, dialect=dialect,
                               source=source, sink=sink,
                               sample_text=sample)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_onboard(bundle, lang=normalize_lang(lang))
