"""Deterministic Avro / JSON Schema compatibility diff for topics.

schema_drift reads SQL DDL; the CDC and Kafka world declares its
shapes in Avro schemas and JSON Schema instead.  Paste the old and new
documents (auto-detected: an Avro ``record`` with ``fields``, or a
JSON Schema with ``properties``) and every change is graded against the
registry's compatibility modes:

* **BACKWARD** — the new schema must read old data: adding a field
  without a default breaks it;
* **FORWARD** — old readers must survive new data: removing a field
  that had no default breaks it;
* type changes pass only along Avro's documented promotions
  (int→long→float→double, string↔bytes) or when a union widens by
  ``null``.

Severity is judged against the *selected* mode: a change that breaks it
is **breaking**, one that only breaks the other mode is **risk**, the
rest are **info**.  No registry connection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["SchemaDiffReport", "SchemaFinding", "diff_topic_schemas"]

_MODES = ("backward", "forward", "full")
_PROMOTIONS = {("int", "long"), ("int", "float"), ("int", "double"),
               ("long", "float"), ("long", "double"), ("float", "double"),
               ("string", "bytes"), ("bytes", "string")}


@dataclass
class SchemaFinding:
    kind: str            # field_added | field_removed | type_changed |
    #                      requirement_changed
    severity: str        # breaking | risk | info
    fld: str
    old: str = ""
    new: str = ""
    breaks: list[str] = field(default_factory=list)  # modes broken

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity,
                "field": self.fld, "old": self.old, "new": self.new,
                "breaks": list(self.breaks)}


@dataclass
class SchemaDiffReport:
    flavor: str          # avro | jsonschema
    mode: str            # backward | forward | full
    fields_old: int = 0
    fields_new: int = 0
    findings: list[SchemaFinding] = field(default_factory=list)

    @property
    def compatible(self) -> bool:
        return not any(f.severity == "breaking" for f in self.findings)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings, ("breaking", "risk", "info"))

    def to_dict(self) -> dict[str, Any]:
        return {"flavor": self.flavor, "mode": self.mode,
                "fields_old": self.fields_old,
                "fields_new": self.fields_new,
                "compatible": self.compatible,
                "counts": self.counts(),
                "findings": [f.to_dict() for f in self.findings]}


@dataclass
class _Field:
    name: str
    type_repr: str
    base_types: frozenset[str]     # union members, lowered
    has_default: bool
    required: bool = True          # JSON Schema only


def _type_repr(t: Any) -> str:
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        return "[" + ", ".join(sorted(_type_repr(x) for x in t)) + "]"
    if isinstance(t, dict):
        return str(t.get("type") or "?")
    return str(t)


def _base_types(t: Any) -> frozenset[str]:
    if isinstance(t, str):
        return frozenset([t.lower()])
    if isinstance(t, list):
        out: set[str] = set()
        for x in t:
            out |= _base_types(x)
        return frozenset(out)
    if isinstance(t, dict):
        return frozenset([str(t.get("type") or "?").lower()])
    return frozenset(["?"])


def _parse(text: str, what: str) -> tuple[str, dict[str, _Field]]:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{what}: not valid JSON ({exc})")
    if not isinstance(doc, dict):
        raise ValueError(f"{what}: the schema must be a JSON object")
    if doc.get("type") == "record" and isinstance(doc.get("fields"), list):
        fields: dict[str, _Field] = {}
        for f in doc["fields"]:
            name = str(f.get("name") or "")
            if not name:
                raise ValueError(f"{what}: every Avro field needs a name")
            fields[name] = _Field(
                name=name, type_repr=_type_repr(f.get("type")),
                base_types=_base_types(f.get("type")),
                has_default="default" in f)
        return "avro", fields
    if isinstance(doc.get("properties"), dict):
        required = {str(r) for r in (doc.get("required") or [])}
        fields = {}
        for name, spec in doc["properties"].items():
            t = spec.get("type") if isinstance(spec, dict) else None
            fields[str(name)] = _Field(
                name=str(name), type_repr=_type_repr(t or "?"),
                base_types=_base_types(t or "?"),
                has_default=isinstance(spec, dict) and "default" in spec,
                required=str(name) in required)
        return "jsonschema", fields
    raise ValueError(f"{what}: neither an Avro record (type/fields) nor "
                     "a JSON Schema (properties)")


def _type_ok(old: _Field, new: _Field) -> bool:
    if old.base_types == new.base_types:
        return True
    # a union widening by null only
    if new.base_types >= old.base_types and \
            new.base_types - old.base_types <= {"null"}:
        return True
    olds = old.base_types - {"null"}
    news = new.base_types - {"null"}
    if len(olds) == 1 and len(news) == 1:
        return (next(iter(olds)), next(iter(news))) in _PROMOTIONS
    return False


def diff_topic_schemas(old_text: str, new_text: str,
                       mode: str = "backward") -> SchemaDiffReport:
    """Two schema documents → compatibility findings for *mode*."""
    mode = (mode or "backward").lower()
    if mode not in _MODES:
        raise ValueError(f"mode must be one of {_MODES}")
    old_flavor, old_fields = _parse(old_text, "old schema")
    new_flavor, new_fields = _parse(new_text, "new schema")
    if old_flavor != new_flavor:
        raise ValueError(f"schema flavors differ: old is {old_flavor}, "
                         f"new is {new_flavor}")

    report = SchemaDiffReport(flavor=old_flavor, mode=mode,
                              fields_old=len(old_fields),
                              fields_new=len(new_fields))
    checked = ({"backward", "forward"} if mode == "full" else {mode})

    def add(kind: str, fld: str, old: str, new: str,
            breaks: set[str]) -> None:
        if breaks & checked:
            severity = "breaking"
        elif breaks:
            severity = "risk"
        else:
            severity = "info"
        report.findings.append(SchemaFinding(
            kind=kind, severity=severity, fld=fld, old=old, new=new,
            breaks=sorted(breaks)))

    for name, nf in new_fields.items():
        if name in old_fields:
            continue
        optional = nf.has_default or "null" in nf.base_types or \
            (old_flavor == "jsonschema" and not nf.required)
        add("field_added", name, "", nf.type_repr,
            set() if optional else {"backward"})
    for name, of in old_fields.items():
        if name in new_fields:
            continue
        optional = of.has_default or "null" in of.base_types or \
            (old_flavor == "jsonschema" and not of.required)
        add("field_removed", name, of.type_repr, "",
            set() if optional else {"forward"})
    for name, of in old_fields.items():
        nf = new_fields.get(name)
        if nf is None:
            continue
        if not _type_ok(of, nf):
            add("type_changed", name, of.type_repr, nf.type_repr,
                {"backward", "forward"})
        elif of.type_repr != nf.type_repr:
            add("type_changed", name, of.type_repr, nf.type_repr, set())
        if old_flavor == "jsonschema" and not of.required and nf.required:
            add("requirement_changed", name, "optional", "required",
                {"backward"})

    order = {"breaking": 0, "risk": 1, "info": 2}
    report.findings.sort(key=lambda f: (order[f.severity], f.kind, f.fld))
    return report
