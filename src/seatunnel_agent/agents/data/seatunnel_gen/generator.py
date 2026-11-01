"""Deterministic SeaTunnel job-config generation from table DDL.

config_lint checks a config, config_diff compares two, config_migrate
ports one — but nobody generates the first one.  Paste the table's
CREATE TABLE DDL (schema_drift parser reused), name the source and sink
connectors (config_lint's connector catalog reused), and the draft
emits a complete env/source/sink HOCON: required parameters filled from
the table where their names say so (database/table/topic), from the
catalog's documented examples otherwise — every example-filled value is
listed as a placeholder to replace.  The draft is linted by config_lint
before it is returned, so it parses and misses no required parameter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ConfigDraft", "generate_config"]

_CDC_RE = re.compile(r"-cdc$", re.IGNORECASE)
_DB_PARAMS = {"database", "database-name", "database_name"}
_TABLE_PARAMS = {"table", "table-name", "table_name"}
_FULL_TABLE_PARAMS = {"table_name"}      # Hive wants db.table in one param
_TOPIC_PARAMS = {"topic"}


@dataclass
class ConfigDraft:
    source: str
    sink: str
    table: str
    columns: int
    job_mode: str
    hocon_text: str = ""
    placeholders: list[str] = field(default_factory=list)  # "section.param"
    filled: list[str] = field(default_factory=list)        # auto-filled
    lint_errors: int = 0
    lint_warns: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "sink": self.sink,
                "table": self.table, "columns": self.columns,
                "job_mode": self.job_mode,
                "hocon_text": self.hocon_text,
                "placeholders": list(self.placeholders),
                "filled": list(self.filled),
                "lint_errors": self.lint_errors,
                "lint_warns": self.lint_warns,
                "warnings": list(self.warnings)}


def _resolve_connector(name: str, role: str):
    from seatunnel_agent.common.connector_docs import CONNECTOR_DOCS

    by_lower = {k.lower(): k for k in CONNECTOR_DOCS}
    key = by_lower.get((name or "").strip().lower())
    if key is None:
        known = ", ".join(sorted(CONNECTOR_DOCS))
        raise ValueError(f"unknown {role} connector '{name}' — known: "
                         f"{known}")
    doc = CONNECTOR_DOCS[key]
    if doc.connector_type not in (role, "both"):
        raise ValueError(f"'{key}' is a {doc.connector_type} connector — "
                         f"it cannot be the {role}")
    return key, doc


def _example_value(param) -> str:
    """The raw right-hand side of the documented example, or a stub."""
    _, _, rhs = (param.example or "").partition("=")
    rhs = rhs.strip()
    return rhs if rhs else '"<FILL_ME>"'


def _smart_fill(param_name: str, db: str, table: str,
                full: str) -> str | None:
    low = param_name.lower()
    if low in _FULL_TABLE_PARAMS and full:
        return f'"{full}"'
    if low in _DB_PARAMS and db:
        return f'"{db}"'
    if low in _TABLE_PARAMS and table:
        return f'"{table}"'
    if low in _TOPIC_PARAMS and table:
        return f'"{table}"'
    return None


def _block(doc, key: str, section: str, db: str, table: str, full: str,
           extra: list[str], draft: ConfigDraft) -> list[str]:
    lines = [f"  {key} {{"]
    for p in doc.required_params:
        value = _smart_fill(p.name, db, table, full)
        if value is not None:
            draft.filled.append(f"{section}.{p.name}")
        else:
            value = _example_value(p)
            draft.placeholders.append(f"{section}.{p.name}")
        name = f'"{p.name}"' if "." in p.name or "-" in p.name else p.name
        lines.append(f"    {name} = {value}")
    lines.extend(f"    {e}" for e in extra)
    lines.append("  }")
    return lines


def generate_config(ddl_text: str, source: str, sink: str,
                    dialect: str = "hive", job_mode: str = "",
                    parallelism: int = 2) -> ConfigDraft:
    """CREATE TABLE DDL + connector pair → linted SeaTunnel HOCON."""
    from seatunnel_agent.agents.data.config_lint import lint_text
    from seatunnel_agent.agents.data.schema_drift.differ import (
        parse_schema_script,
    )

    if parallelism < 1:
        raise ValueError("parallelism must be positive")
    if job_mode and job_mode.upper() not in ("BATCH", "STREAMING"):
        raise ValueError("job_mode must be BATCH or STREAMING")
    src_key, src_doc = _resolve_connector(source, "source")
    sink_key, sink_doc = _resolve_connector(sink, "sink")
    tables, warnings = parse_schema_script(ddl_text, dialect)
    if not tables:
        raise ValueError("no CREATE TABLE found in the DDL"
                         + (f" ({warnings[0]})" if warnings else ""))
    full = next(iter(tables))
    schema = tables[full]
    if len(tables) > 1:
        warnings.append(f"{len(tables)} tables in the DDL — the job is "
                        f"generated for the first ({full})")
    db, _, table = full.rpartition(".")
    cols = [c for c in schema.columns.values() if not c.is_partition]

    mode = (job_mode.upper() if job_mode
            else "STREAMING" if _CDC_RE.search(src_key) else "BATCH")
    draft = ConfigDraft(source=src_key, sink=sink_key, table=full,
                        columns=len(cols), job_mode=mode,
                        warnings=list(warnings))

    result_table = table or full
    lines = ["env {", f"  parallelism = {parallelism}",
             f'  job.mode = "{mode}"', "}", "", "source {"]
    lines += _block(src_doc, src_key, "source", db, table, full,
                    [f'plugin_output = "{result_table}"'], draft)
    lines += ["}", "", "sink {"]
    lines += _block(sink_doc, sink_key, "sink", db, table, full,
                    [f'plugin_input = "{result_table}"'], draft)
    lines += ["}", ""]
    draft.hocon_text = "\n".join(lines)

    lint = lint_text(draft.hocon_text, name=f"{src_key}->{sink_key}")
    counts = lint.counts()
    draft.lint_errors = counts.get("error", 0)
    draft.lint_warns = counts.get("warn", 0)
    if draft.lint_errors:   # round-trip guard — the draft must lint clean
        worst = lint.findings[0]
        raise ValueError("generated config failed config_lint: "
                         f"{worst.kind} ({worst.section}.{worst.param})")
    return draft
