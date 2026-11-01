"""消息 Schema 建表 — Avro record / JSON Schema → 落地 CREATE TABLE.

Deterministic core: map the schema's types to Hive or Doris DDL —
logicalType wins (decimal/date/timestamp), [null,T] unions unwrap as
nullable, multi-type unions land as STRING and are named, Hive gets
real ARRAY/MAP/STRUCT while Doris gets JSON plus a key/bucket stub, doc
becomes COMMENT — then round-trip the DDL through schema_drift's parser
(same column count) before returning.  topic_schema diffs two schema
versions; this lands one as the table; seatunnel_gen turns the table
into the sync job.  No registry or database connection.
"""

from .converter import DdlDraft, convert_schema
from .report import render_markdown

__all__ = [
    "DdlDraft",
    "convert_schema",
    "render_markdown",
]
