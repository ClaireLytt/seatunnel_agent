"""Deterministic CREATE TABLE generation from a message schema.

The topic has a schema; the landing table gets typed by hand — and the
hand-typed DDL drifts from day one.  Paste the Avro record (or JSON
Schema) and the converter emits the CREATE TABLE for Hive or Doris:

* Avro primitives map directly (long→BIGINT, bytes→BINARY, …);
  ``logicalType`` wins over the raw type (decimal→DECIMAL(p,s),
  date→DATE, timestamp-millis/micros→TIMESTAMP);
* ``[null, T]`` unions mean nullable and unwrap to T; any other union
  lands as STRING with a lossy note;
* complex types: Hive gets real ARRAY / MAP / STRUCT; Doris gets JSON
  with a lossy note (plus a DUPLICATE KEY stub on the first column);
* ``doc`` becomes COMMENT, enums become STRING with the symbols in the
  comment.

The DDL round-trips through schema_drift's parser (same column count)
before it is returned.  topic_schema diffs two schema versions; this
turns one version into the table.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

__all__ = ["DdlDraft", "convert_schema"]

_DIALECTS = ("hive", "doris")

_AVRO_PRIMITIVE = {
    "hive": {"string": "STRING", "bytes": "BINARY", "int": "INT",
             "long": "BIGINT", "float": "FLOAT", "double": "DOUBLE",
             "boolean": "BOOLEAN"},
    "doris": {"string": "STRING", "bytes": "STRING", "int": "INT",
              "long": "BIGINT", "float": "FLOAT", "double": "DOUBLE",
              "boolean": "BOOLEAN"},
}
_LOGICAL = {
    "hive": {"date": "DATE", "timestamp-millis": "TIMESTAMP",
             "timestamp-micros": "TIMESTAMP"},
    "doris": {"date": "DATE", "timestamp-millis": "DATETIME",
              "timestamp-micros": "DATETIME"},
}
_JSONSCHEMA = {
    "hive": {"integer": "BIGINT", "number": "DOUBLE", "string": "STRING",
             "boolean": "BOOLEAN"},
    "doris": {"integer": "BIGINT", "number": "DOUBLE", "string": "STRING",
              "boolean": "BOOLEAN"},
}
_JS_FORMAT = {
    "hive": {"date": "DATE", "date-time": "TIMESTAMP"},
    "doris": {"date": "DATE", "date-time": "DATETIME"},
}


@dataclass
class ColumnDraft:
    name: str
    source_type: str
    ddl_type: str
    nullable: bool = True
    comment: str = ""
    note: str = ""       # i18n suffix for a lossy/notable mapping

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "source_type": self.source_type,
                "ddl_type": self.ddl_type, "nullable": self.nullable,
                "comment": self.comment, "note": self.note}


@dataclass
class DdlDraft:
    flavor: str          # avro | jsonschema
    dialect: str
    table: str
    columns: list[ColumnDraft] = field(default_factory=list)
    ddl_text: str = ""
    lossy: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"flavor": self.flavor, "dialect": self.dialect,
                "table": self.table,
                "columns_total": len(self.columns),
                "lossy": self.lossy,
                "columns": [c.to_dict() for c in self.columns],
                "ddl_text": self.ddl_text}


def _avro_type(t: Any, dialect: str) -> tuple[str, str, bool]:
    """Avro type node → (ddl type, note, nullable)."""
    if isinstance(t, list):
        members = [m for m in t if m != "null"]
        nullable = len(members) < len(t)
        if len(members) == 1:
            ddl, note, _ = _avro_type(members[0], dialect)
            return ddl, note, nullable
        return "STRING", "union_lossy", True
    if isinstance(t, dict):
        logical = t.get("logicalType")
        if logical == "decimal":
            p = int(t.get("precision") or 38)
            s = int(t.get("scale") or 0)
            return f"DECIMAL({p},{s})", "", True
        if logical in _LOGICAL[dialect]:
            return _LOGICAL[dialect][logical], "", True
        kind = t.get("type")
        if kind == "enum":
            symbols = ", ".join(str(s) for s in (t.get("symbols") or []))
            return "STRING", f"enum:{symbols}", True
        if kind == "fixed":
            return _AVRO_PRIMITIVE[dialect]["bytes"], "", True
        if kind == "array":
            inner, _, _ = _avro_type(t.get("items"), dialect)
            if dialect == "hive":
                return f"ARRAY<{inner}>", "", True
            return "JSON", "complex_lossy", True
        if kind == "map":
            inner, _, _ = _avro_type(t.get("values"), dialect)
            if dialect == "hive":
                return f"MAP<STRING,{inner}>", "", True
            return "JSON", "complex_lossy", True
        if kind == "record":
            if dialect == "hive":
                inner = ", ".join(
                    f"{f.get('name')}:"
                    f"{_avro_type(f.get('type'), dialect)[0]}"
                    for f in (t.get("fields") or []))
                return f"STRUCT<{inner}>", "", True
            return "JSON", "complex_lossy", True
        if isinstance(kind, str) and kind in _AVRO_PRIMITIVE[dialect]:
            return _AVRO_PRIMITIVE[dialect][kind], "", True
        return "STRING", "unknown_lossy", True
    if isinstance(t, str):
        if t in _AVRO_PRIMITIVE[dialect]:
            return _AVRO_PRIMITIVE[dialect][t], "", False
        return "STRING", "unknown_lossy", True
    return "STRING", "unknown_lossy", True


def _js_type(spec: Any, dialect: str) -> tuple[str, str]:
    if not isinstance(spec, dict):
        return "STRING", "unknown_lossy"
    t = spec.get("type")
    if t == "string" and spec.get("format") in _JS_FORMAT[dialect]:
        return _JS_FORMAT[dialect][spec["format"]], ""
    if isinstance(t, str) and t in _JSONSCHEMA[dialect]:
        return _JSONSCHEMA[dialect][t], ""
    if t in ("array", "object"):
        if dialect == "hive" and t == "array":
            return "ARRAY<STRING>", "complex_lossy"
        return ("STRING" if dialect == "hive" else "JSON"), "complex_lossy"
    return "STRING", "unknown_lossy"


def convert_schema(schema_text: str, table: str = "",
                   dialect: str = "hive") -> DdlDraft:
    """Avro record / JSON Schema → CREATE TABLE draft, round-tripped."""
    if dialect not in _DIALECTS:
        raise ValueError(f"dialect must be one of {_DIALECTS}")
    try:
        doc = json.loads(schema_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"schema: not valid JSON ({exc})")
    if not isinstance(doc, dict):
        raise ValueError("the schema must be a JSON object")

    columns: list[ColumnDraft] = []
    if doc.get("type") == "record" and isinstance(doc.get("fields"), list):
        flavor = "avro"
        default_table = ".".join(
            p for p in (doc.get("namespace"), doc.get("name")) if p)
        for f in doc["fields"]:
            name = str(f.get("name") or "")
            if not name:
                raise ValueError("every Avro field needs a name")
            avro_type = f.get("type")
            ddl, note, nullable = _avro_type(avro_type, dialect)
            columns.append(ColumnDraft(
                name=name,
                source_type=(avro_type if isinstance(avro_type, str)
                             else json.dumps(avro_type)),
                ddl_type=ddl, nullable=nullable,
                comment=str(f.get("doc") or ""), note=note))
    elif isinstance(doc.get("properties"), dict):
        flavor = "jsonschema"
        default_table = str(doc.get("title") or "")
        for name, spec in doc["properties"].items():
            ddl, note = _js_type(spec, dialect)
            columns.append(ColumnDraft(
                name=str(name),
                source_type=str(spec.get("type") if isinstance(spec, dict)
                                else "?"),
                ddl_type=ddl,
                comment=str(spec.get("description") or ""
                            ) if isinstance(spec, dict) else "",
                note=note))
    else:
        raise ValueError("neither an Avro record (type/fields) nor a "
                         "JSON Schema (properties)")
    if not columns:
        raise ValueError("the schema declares no fields")

    draft = DdlDraft(flavor=flavor, dialect=dialect,
                     table=(table or default_table or "landing_table")
                     .strip(), columns=columns,
                     lossy=sum(1 for c in columns if c.note))

    lines = [f"CREATE TABLE {draft.table} ("]
    body = []
    for c in columns:
        comment = c.comment
        if c.note.startswith("enum:"):
            allowed = c.note[5:]
            comment = (comment + " " if comment else "") + f"[{allowed}]"
        piece = f"  {c.name} {c.ddl_type}"
        if comment:
            piece += " COMMENT '" + comment.replace("'", "''") + "'"
        body.append(piece)
    lines.append(",\n".join(body))
    if dialect == "doris":
        lines.append(f") DUPLICATE KEY ({columns[0].name})")
        lines.append(f"DISTRIBUTED BY HASH ({columns[0].name}) "
                     "BUCKETS 8;")
    else:
        lines.append(") STORED AS ORC;")
    draft.ddl_text = "\n".join(lines)

    # round-trip guard: the DDL must parse with the same column count
    from seatunnel_agent.agents.data.schema_drift.differ import (
        parse_schema_script,
    )

    parsed, _ = parse_schema_script(draft.ddl_text,
                                    "hive" if dialect == "hive"
                                    else "doris")
    if not parsed:
        raise ValueError("internal: the generated DDL failed to parse")
    schema = next(iter(parsed.values()))
    if len(schema.columns) != len(columns):
        raise ValueError("internal: the generated DDL lost columns in "
                         "the round-trip")
    return draft
