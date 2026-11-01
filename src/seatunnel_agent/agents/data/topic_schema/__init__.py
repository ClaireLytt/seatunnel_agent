"""消息 Schema 对比 — 两版 Avro/JSON Schema → 注册中心级兼容结论.

Deterministic core: parse both documents (Avro record or JSON Schema,
auto-detected), grade every field change against the registry's
compatibility modes — BACKWARD (adding a defaultless field breaks it),
FORWARD (removing a defaultless field breaks it), types only along
Avro's promotions or a union widening by null.  schema_drift reads SQL
DDL; this reads the messaging world's schemas.  No registry connection.
"""

from .differ import SchemaDiffReport, SchemaFinding, diff_topic_schemas
from .report import render_markdown

__all__ = [
    "SchemaDiffReport",
    "SchemaFinding",
    "diff_topic_schemas",
    "render_markdown",
]
