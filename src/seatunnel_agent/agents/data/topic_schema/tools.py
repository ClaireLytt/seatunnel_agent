"""Chat/MCP tool entry point for the topic-schema differ.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def topic_schema_diff(old_schema: str, new_schema: str,
                      mode: str = "backward", lang: str = "") -> str:
    """消息 Schema 兼容性对比（确定性）：粘贴两版 Avro record 或 JSON
    Schema,按注册中心规则分级——BACKWARD 下新增无默认值字段即破坏,
    FORWARD 下删除无默认值字段即破坏,类型只认 Avro 升格链或 union 加
    null;可选 full 同查双向。发布前最后一道检查。不连注册中心。"""
    from seatunnel_agent.agents.data.topic_schema import (
        diff_topic_schemas,
        render_markdown,
    )

    if not (old_schema or "").strip() or not (new_schema or "").strip():
        return "两版 Schema 都不能为空 / both schemas are required"
    try:
        report = diff_topic_schemas(old_schema, new_schema, mode=mode)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(report, lang=normalize_lang(lang))
