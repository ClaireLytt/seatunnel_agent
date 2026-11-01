"""Deterministic DQC-rule draft generation from a data sample.

data_quality runs rule YAML against tables, but someone has to write
that YAML first, and nobody does.  Paste a sample of the table
(sample_profile's parser and column profiles reused) and the draft
promises what the data already keeps:

* ``row_count`` — min 1 plus a change guard (``max_change_pct``);
* ``null_rate`` — per column, the observed null share plus head-room;
* ``unique`` — columns that are 100% distinct in the sample and look
  like keys (integer or ``*id*`` names);
* ``enum_domain`` — low-cardinality string columns pin their observed
  value set.

The draft round-trips through ``data_quality.parse_rules_text`` before
it is returned, so the output always loads as-is.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

__all__ = ["RuleDraft", "generate_rules"]

_ENUM_MAX_DISTINCT = 12
_ENUM_UNIQUE_PCT = 30.0
_NULL_HEADROOM = 5.0        # percentage points on top of the observed rate
_NULL_SKIP_PCT = 50.0       # columns this hollow get no null_rate promise
_ID_RE = re.compile(r"(^id$|_id$|^.*_no$)", re.IGNORECASE)
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class DraftCheck:
    type: str
    column: str = ""
    columns: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    basis: str = ""          # what in the sample justified it

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "column": self.column,
                "columns": list(self.columns),
                "params": dict(self.params), "basis": self.basis}


@dataclass
class RuleDraft:
    table: str
    rows_sampled: int
    checks: list[DraftCheck] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # columns + why
    yaml_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "rows_sampled": self.rows_sampled,
                "checks_total": len(self.checks),
                "checks": [c.to_dict() for c in self.checks],
                "skipped": list(self.skipped),
                "yaml_text": self.yaml_text}


def _quote(v: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_.\-]+", v or ""):
        return v
    return '"' + (v or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def _render_yaml(table: str, where: str,
                 checks: list[DraftCheck]) -> str:
    lines = ["version: 1", "rules:", f"  - table: {_quote(table)}"]
    if where:
        lines.append(f'    where: "{where}"')
    lines.append("    checks:")
    for c in checks:
        lines.append(f"      - type: {c.type}")
        if c.column:
            lines.append(f"        column: {_quote(c.column)}")
        if c.columns:
            cols = ", ".join(_quote(x) for x in c.columns)
            lines.append(f"        columns: [{cols}]")
        for k, v in c.params.items():
            if k == "allowed":
                vals = ", ".join(_quote(str(x)) for x in v)
                lines.append(f"        allowed: [{vals}]")
            else:
                lines.append(f"        {k}: {v:g}")
    return "\n".join(lines) + "\n"


def generate_rules(headers: list[str], rows: list[dict[str, str | None]],
                   table: str, where: str = "",
                   max_change_pct: float = 50.0) -> RuleDraft:
    """Sample rows + table name → loadable DQC rule YAML draft."""
    from seatunnel_agent.agents.data.data_quality.rules import (
        parse_rules_text,
    )
    from seatunnel_agent.agents.data.sample_profile import profile_rows

    if not (table or "").strip():
        raise ValueError("table name must not be empty")
    if not headers or not rows:
        raise ValueError("the sample needs a header and at least one row")
    if max_change_pct <= 0:
        raise ValueError("max_change_pct must be positive")

    profiles = profile_rows(headers, rows).columns
    draft = RuleDraft(table=table.strip(), rows_sampled=len(rows))
    draft.checks.append(DraftCheck(
        type="row_count",
        params={"min": 1, "max_change_pct": max_change_pct},
        basis=f"{len(rows)} rows sampled"))

    for p in profiles:
        if not _IDENT_RE.match(p.name):
            draft.skipped.append(
                f"{p.name}: not a plain identifier — rename before gating")
            continue
        if p.null_pct > _NULL_SKIP_PCT:
            draft.skipped.append(
                f"{p.name}: {p.null_pct:g}% null — too hollow to promise")
            continue
        cap = min(100.0, math.ceil(p.null_pct) + _NULL_HEADROOM)
        draft.checks.append(DraftCheck(
            type="null_rate", column=p.name, params={"max_pct": cap},
            basis=f"observed {p.null_pct:g}% null"))
        values = [str(r[p.name]) for r in rows
                  if r.get(p.name) not in (None, "")]
        distinct = len(set(values))
        if (values and distinct == len(values)
                and (p.kind == "integer" or _ID_RE.search(p.name))):
            draft.checks.append(DraftCheck(
                type="unique", columns=[p.name],
                basis="100% distinct in the sample"))
        elif (values and p.kind not in ("integer", "decimal")
                and (distinct <= _ENUM_MAX_DISTINCT
                     or p.unique_pct < _ENUM_UNIQUE_PCT)
                and distinct <= _ENUM_MAX_DISTINCT):
            draft.checks.append(DraftCheck(
                type="enum_domain", column=p.name,
                params={"allowed": sorted(set(values))},
                basis=f"{distinct} observed value(s)"))

    draft.yaml_text = _render_yaml(draft.table, where, draft.checks)
    _, errors = parse_rules_text(draft.yaml_text)
    if errors:   # round-trip guard: the draft must load as-is
        raise ValueError("generated YAML failed to load: " + errors[0])
    return draft
