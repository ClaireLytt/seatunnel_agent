# -*- coding: utf-8 -*-
"""Deterministic SeaTunnel config lint core.

Finding kinds (severity):
  syntax_error        (error)  HOCON does not parse
  missing_section     (error)  no source / sink block
  empty_section       (error)  source/sink block has no connector
  unknown_connector   (warn)   name not in the doc catalog (+ suggestion)
  role_mismatch       (error)  strictly-source connector in sink block etc.
  missing_required    (error)  documented required param absent
  unknown_param       (warn)   param not documented (+ suggestion)
  type_mismatch       (warn)   value type differs from the documented type
  enum_mismatch       (error)  value outside the documented enum values
  bad_job_mode        (error)  job.mode not BATCH/STREAMING
  cdc_requires_stream (error)  CDC source with job.mode = BATCH
  bad_parallelism     (error)  parallelism not a positive int
  unresolved_subst    (error)  ${...} substitution cannot resolve
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..connector_docs import CONNECTOR_DOCS

SEVERITIES = ("error", "warn", "info")
_SEV_RANK = {"info": 1, "warn": 2, "error": 3}

# framework-level keys legal inside any connector block
_FRAMEWORK_KEYS = frozenset({
    "result_table_name", "source_table_name",
    "plugin_output", "plugin_input", "parallelism",
})

# transforms are not covered by CONNECTOR_DOCS — recognised, never linted
_KNOWN_TRANSFORMS = frozenset({
    "sql", "fieldmapper", "filter", "replace", "split", "copy",
    "jsonpath", "dynamiccompile", "llm",
})

_JOB_MODES = ("BATCH", "STREAMING")


@dataclass
class LintFinding:
    kind: str
    severity: str                  # error | warn | info
    section: str = ""              # env | source | transform | sink
    connector: str = ""
    param: str = ""
    message_params: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity,
                "section": self.section, "connector": self.connector,
                "param": self.param, "params": dict(self.message_params)}


@dataclass
class LintResult:
    name: str
    findings: list[LintFinding] = field(default_factory=list)
    sections_found: list[str] = field(default_factory=list)
    connectors: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {level: 0 for level in SEVERITIES}
        for f in self.findings:
            out[f.severity] += 1
        out["total"] = len(self.findings)
        return out

    @property
    def ok(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "counts": self.counts(),
                "sections_found": list(self.sections_found),
                "connectors": list(self.connectors),
                "findings": [f.to_dict() for f in self.findings]}


def _doc_key(name: str) -> str | None:
    if name in CONNECTOR_DOCS:
        return name
    lower = name.lower()
    for key in CONNECTOR_DOCS:
        if key.lower() == lower:
            return key
    return None


def _suggest(name: str, candidates: list[str]) -> str:
    match = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
    return match[0] if match else ""


def _type_ok(value: Any, declared: str) -> bool:
    declared = (declared or "").lower()
    if declared == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "string" or declared == "enum":
        return isinstance(value, str)
    if declared == "object":
        return isinstance(value, dict) or hasattr(value, "items")
    if declared == "array":
        return isinstance(value, (list, tuple))
    return True  # unknown declared type: never flag


def _as_items(node: Any) -> list[tuple[str, Any]]:
    """Connector blocks of a section as (name, params) pairs."""
    if node is None or not hasattr(node, "items"):
        return []
    return [(str(k), v) for k, v in node.items()]


def _lint_connector(result: LintResult, section: str, name: str,
                    params: Any) -> None:
    key = _doc_key(name)
    if key is None:
        suggestion = _suggest(name, list(CONNECTOR_DOCS))
        result.findings.append(LintFinding(
            kind="unknown_connector", severity="warn", section=section,
            connector=name, message_params={"suggestion": suggestion}))
        return
    doc = CONNECTOR_DOCS[key]
    if doc.connector_type in ("source", "sink") and \
            doc.connector_type != section:
        result.findings.append(LintFinding(
            kind="role_mismatch", severity="error", section=section,
            connector=name,
            message_params={"role": doc.connector_type}))

    present: dict[str, Any] = {}
    if hasattr(params, "items"):
        present = {str(k): v for k, v in params.items()}
    documented = {p.name: p for p in doc.required_params + doc.optional_params}

    for p in doc.required_params:
        if p.name not in present:
            result.findings.append(LintFinding(
                kind="missing_required", severity="error", section=section,
                connector=name, param=p.name,
                message_params={"example": p.example}))

    for raw_key, value in present.items():
        if raw_key in _FRAMEWORK_KEYS:
            continue
        p = documented.get(raw_key)
        if p is None:
            suggestion = _suggest(raw_key, list(documented))
            result.findings.append(LintFinding(
                kind="unknown_param", severity="warn", section=section,
                connector=name, param=raw_key,
                message_params={"suggestion": suggestion}))
            continue
        if p.enum_values and isinstance(value, str) \
                and value not in p.enum_values:
            result.findings.append(LintFinding(
                kind="enum_mismatch", severity="error", section=section,
                connector=name, param=raw_key,
                message_params={"value": str(value),
                                "allowed": ", ".join(p.enum_values)}))
        elif not _type_ok(value, p.type):
            result.findings.append(LintFinding(
                kind="type_mismatch", severity="warn", section=section,
                connector=name, param=raw_key,
                message_params={"declared": p.type,
                                "actual": type(value).__name__}))


def _lint_env(result: LintResult, env: Any, source_names: list[str]) -> None:
    get = env.get if hasattr(env, "get") else (lambda *_: None)
    job_mode = get("job.mode", None)
    if job_mode is not None and str(job_mode).upper() not in _JOB_MODES:
        result.findings.append(LintFinding(
            kind="bad_job_mode", severity="error", section="env",
            param="job.mode",
            message_params={"value": str(job_mode),
                            "allowed": "/".join(_JOB_MODES)}))
    cdc = [n for n in source_names if n.lower().endswith("-cdc")]
    if cdc and str(job_mode or "BATCH").upper() == "BATCH":
        result.findings.append(LintFinding(
            kind="cdc_requires_stream", severity="error", section="env",
            connector=cdc[0], param="job.mode"))
    parallelism = get("parallelism", None)
    if parallelism is not None and (
            isinstance(parallelism, bool)
            or not isinstance(parallelism, int) or parallelism <= 0):
        result.findings.append(LintFinding(
            kind="bad_parallelism", severity="error", section="env",
            param="parallelism",
            message_params={"value": str(parallelism)}))


def lint_text(text: str, name: str = "<inline>") -> LintResult:
    from pyhocon import ConfigFactory
    from pyhocon.exceptions import ConfigException

    result = LintResult(name=name)
    try:
        config = ConfigFactory.parse_string(text)
    except ConfigException as exc:
        kind = ("unresolved_subst"
                if "substitution" in str(exc).lower() else "syntax_error")
        result.findings.append(LintFinding(
            kind=kind, severity="error",
            message_params={"detail": str(exc)[:300]}))
        return result
    except Exception as exc:  # noqa: BLE001 — pyhocon raises bare exceptions too
        result.findings.append(LintFinding(
            kind="syntax_error", severity="error",
            message_params={"detail": str(exc)[:300]}))
        return result

    sections: dict[str, Any] = {}
    for section in ("env", "source", "transform", "sink"):
        node = config.get(section, None)
        if node is not None:
            sections[section] = node
            result.sections_found.append(section)

    for required in ("source", "sink"):
        if required not in sections:
            result.findings.append(LintFinding(
                kind="missing_section", severity="error", section=required))

    source_names: list[str] = []
    for section in ("source", "sink"):
        node = sections.get(section)
        if node is None:
            continue
        blocks = _as_items(node)
        if not blocks:
            result.findings.append(LintFinding(
                kind="empty_section", severity="error", section=section))
            continue
        for conn_name, params in blocks:
            result.connectors.append(f"{section}:{conn_name}")
            if section == "source":
                source_names.append(conn_name)
            _lint_connector(result, section, conn_name, params)

    # transforms have no doc catalog — only flag names nobody has heard of
    for conn_name, _params in _as_items(sections.get("transform")):
        result.connectors.append(f"transform:{conn_name}")
        if conn_name.lower() not in _KNOWN_TRANSFORMS:
            result.findings.append(LintFinding(
                kind="unknown_connector", severity="info",
                section="transform", connector=conn_name,
                message_params={"suggestion": _suggest(
                    conn_name.lower(), sorted(_KNOWN_TRANSFORMS))}))

    if "env" in sections:
        _lint_env(result, sections["env"], source_names)

    result.findings.sort(
        key=lambda f: (-_SEV_RANK[f.severity], f.section, f.connector,
                       f.param))
    return result


def lint_file(path: str | Path) -> LintResult:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        result = LintResult(name=str(path))
        result.findings.append(LintFinding(
            kind="syntax_error", severity="error",
            message_params={"detail": f"无法读取: {exc}"}))
        return result
    return lint_text(text, name=str(path))


def collect_conf_files(directory: str | Path) -> list[Path]:
    return sorted(p for p in Path(directory).rglob("*.conf") if p.is_file())


def lint_dir(directory: str | Path) -> list[LintResult]:
    return [lint_file(p) for p in collect_conf_files(directory)]
