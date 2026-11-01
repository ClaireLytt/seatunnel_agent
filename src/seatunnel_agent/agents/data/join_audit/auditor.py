"""Deterministic join-quality audit over two pasted row sets.

A join that silently drops a third of the rows — or multiplies them —
is the most common invisible warehouse incident.  Paste both sides
(sample_profile's parser reused) and the join key(s): the audit
computes the match rate of each side, the orphan keys, the null-key
share, and the row explosion a real join would produce, with the keys
that blow up the most:

* JA001 high — many-to-many keys (duplicated on both sides): the join
  multiplies rows, factor and worst keys named;
* JA002 — left rows that find no match (medium at < 90%, high at
  < 50% match rate);
* JA003 — right rows that no left row reaches (same grading);
* JA004 — null/empty join keys (low under 1%, medium from 1%).

Keys: ``k`` when both sides share the name, ``lk=rk`` to map, comma to
combine several.  No database connection — the audit runs on the rows.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["JoinAuditReport", "JoinFinding", "audit_join", "parse_keys"]

_MATCH_MED = 0.9
_MATCH_HIGH = 0.5
_NULL_MED = 0.01
_TOP_KEYS = 5


@dataclass
class JoinFinding:
    code: str            # JA001..JA004
    severity: str        # high | medium | low
    side: str            # left | right | both
    detail: str = ""     # worst keys / samples
    value: float = 0.0   # the metric behind the grade

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "side": self.side, "detail": self.detail,
                "value": round(self.value, 4)}


@dataclass
class JoinAuditReport:
    keys: list[tuple[str, str]]
    left_rows: int = 0
    right_rows: int = 0
    left_match_rate: float = 0.0
    right_match_rate: float = 0.0
    joined_rows: int = 0
    explosion: float = 0.0          # joined / matched left rows
    left_null_keys: int = 0
    right_null_keys: int = 0
    findings: list[JoinFinding] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"keys": [{"left": a, "right": b} for a, b in self.keys],
                "left_rows": self.left_rows,
                "right_rows": self.right_rows,
                "left_match_rate": round(self.left_match_rate, 4),
                "right_match_rate": round(self.right_match_rate, 4),
                "joined_rows": self.joined_rows,
                "explosion": round(self.explosion, 4),
                "left_null_keys": self.left_null_keys,
                "right_null_keys": self.right_null_keys,
                "counts": self.counts(),
                "findings": [f.to_dict() for f in self.findings]}


def parse_keys(spec: str) -> list[tuple[str, str]]:
    """``"k"`` / ``"lk=rk"`` / comma-combined → [(left, right), ...]."""
    out: list[tuple[str, str]] = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        left, _, right = part.partition("=")
        out.append((left.strip(), (right or left).strip()))
    if not out:
        raise ValueError("join key must not be empty "
                         "(use 'k' or 'left_key=right_key')")
    return out


def _key_of(row: dict, cols: list[str]) -> tuple | None:
    vals = []
    for c in cols:
        v = row.get(c)
        if v is None or str(v).strip() == "":
            return None
        vals.append(str(v))
    return tuple(vals)


def _grade_match(rate: float) -> str | None:
    if rate < _MATCH_HIGH:
        return "high"
    if rate < _MATCH_MED:
        return "medium"
    return None


def audit_join(left_headers: list[str], left_rows: list[dict],
               right_headers: list[str], right_rows: list[dict],
               keys: list[tuple[str, str]]) -> JoinAuditReport:
    """Two row sets + key mapping → join-quality report."""
    if not left_rows or not right_rows:
        raise ValueError("both sides need at least one row")
    for lk, _ in keys:
        if lk not in left_headers:
            raise ValueError(f"left side has no column '{lk}'")
    for _, rk in keys:
        if rk not in right_headers:
            raise ValueError(f"right side has no column '{rk}'")

    lcols = [lk for lk, _ in keys]
    rcols = [rk for _, rk in keys]
    lkeys = [_key_of(r, lcols) for r in left_rows]
    rkeys = [_key_of(r, rcols) for r in right_rows]
    lcount = Counter(k for k in lkeys if k is not None)
    rcount = Counter(k for k in rkeys if k is not None)

    report = JoinAuditReport(keys=list(keys),
                             left_rows=len(left_rows),
                             right_rows=len(right_rows),
                             left_null_keys=sum(k is None for k in lkeys),
                             right_null_keys=sum(k is None for k in rkeys))

    l_valid = len(left_rows) - report.left_null_keys
    r_valid = len(right_rows) - report.right_null_keys
    l_matched = sum(c for k, c in lcount.items() if k in rcount)
    r_matched = sum(c for k, c in rcount.items() if k in lcount)
    report.left_match_rate = l_matched / l_valid if l_valid else 0.0
    report.right_match_rate = r_matched / r_valid if r_valid else 0.0
    report.joined_rows = sum(c * rcount[k] for k, c in lcount.items()
                             if k in rcount)
    report.explosion = (report.joined_rows / l_matched
                        if l_matched else 0.0)

    def add(code: str, severity: str, side: str, detail: str,
            value: float) -> None:
        report.findings.append(JoinFinding(
            code=code, severity=severity, side=side, detail=detail,
            value=value))

    mn = [(k, lcount[k] * rcount[k]) for k in lcount
          if lcount[k] > 1 and rcount.get(k, 0) > 1]
    if mn:
        worst = sorted(mn, key=lambda kv: -kv[1])[:_TOP_KEYS]
        add("JA001", "high", "both",
            ", ".join(f"{'|'.join(k)} x{v}" for k, v in worst),
            report.explosion)

    sev = _grade_match(report.left_match_rate)
    if sev:
        orphans = [k for k in lcount if k not in rcount][:_TOP_KEYS]
        add("JA002", sev, "left",
            ", ".join("|".join(k) for k in orphans),
            report.left_match_rate)
    sev = _grade_match(report.right_match_rate)
    if sev:
        orphans = [k for k in rcount if k not in lcount][:_TOP_KEYS]
        add("JA003", sev, "right",
            ", ".join("|".join(k) for k in orphans),
            report.right_match_rate)

    for side, nulls, total in (("left", report.left_null_keys,
                                len(left_rows)),
                               ("right", report.right_null_keys,
                                len(right_rows))):
        if nulls:
            share = nulls / total
            add("JA004", "medium" if share >= _NULL_MED else "low",
                side, f"{nulls}/{total}", share)
    order = {"high": 0, "medium": 1, "low": 2}
    report.findings.sort(key=lambda f: (order[f.severity], f.code))
    return report
