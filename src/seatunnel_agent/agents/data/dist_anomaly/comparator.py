"""Deterministic distribution-drift comparison between two data profiles.

Both sides are sample-profile results (``ProfileResult.to_dict()``
shape) — built here from raw CSV/JSONL rows via the sample_profile
facade, or supplied directly as profile JSON.  Per common column the
comparator judges mean shift, null/unique-rate jumps, dominant-kind
changes and top-category share drift (L1 distance plus appeared or
vanished categories); schema-level adds/removes are reported too.
Rule-based thresholds, no database connection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from seatunnel_agent.agents.data.sample_profile import (
    parse_rows,
    profile_rows,
    sample_rows,
)

__all__ = ["DriftFinding", "DriftResult", "compare_profiles", "load_profile"]

# thresholds: (mid, high)
_MEAN_SHIFT = (0.20, 0.50)      # relative |Δmean|
_RATE_JUMP = (10.0, 25.0)       # percentage points (null%/unique%)
_L1_SHIFT = (0.20, 0.40)        # category share L1 distance (0..2)


@dataclass
class DriftFinding:
    code: str          # DA001..
    severity: str      # high / mid / low
    column: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "column": self.column, "detail": self.detail}


@dataclass
class DriftResult:
    baseline_rows: int
    current_rows: int
    columns_compared: int
    findings: list[DriftFinding]

    def to_dict(self) -> dict:
        return {"baseline_rows": self.baseline_rows,
                "current_rows": self.current_rows,
                "columns_compared": self.columns_compared,
                "findings": [f.to_dict() for f in self.findings]}


def load_profile(text: str, max_rows: int = 2000) -> dict:
    """Raw CSV/JSONL rows or a profile JSON → profile dict.

    A JSON object carrying ``columns`` is taken as a ready profile
    (``sampleprofile --format json`` output); anything else is parsed
    and profiled here.
    """
    body = (text or "").strip()
    if body.startswith("{"):
        try:
            obj = json.loads(body)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict) and "columns" in obj:
            return obj
    headers, rows = parse_rows(body)
    return profile_rows(headers, sample_rows(rows, max_rows),
                        total_rows=len(rows)).to_dict()


def _grade(value: float, thresholds: tuple[float, float]) -> str | None:
    mid, high = thresholds
    if value >= high:
        return "high"
    if value >= mid:
        return "mid"
    return None


def _shares(col: dict) -> dict[str, float]:
    non_null = col.get("non_null") or 0
    if not non_null:
        return {}
    return {t["value"]: t["count"] / non_null for t in col.get("top", ())}


def compare_profiles(baseline: dict, current: dict) -> DriftResult:
    base_cols = {c["name"]: c for c in baseline.get("columns", ())}
    cur_cols = {c["name"]: c for c in current.get("columns", ())}
    findings: list[DriftFinding] = []

    for name in base_cols:
        if name not in cur_cols:
            findings.append(DriftFinding("DA001", "high", name,
                                         {"change": "removed"}))
    for name in cur_cols:
        if name not in base_cols:
            findings.append(DriftFinding("DA001", "mid", name,
                                         {"change": "added"}))

    common = [n for n in base_cols if n in cur_cols]
    for name in common:
        b, c = base_cols[name], cur_cols[name]
        findings.extend(_compare_column(name, b, c))

    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code, f.column))
    return DriftResult(
        baseline_rows=baseline.get("total_rows", 0),
        current_rows=current.get("total_rows", 0),
        columns_compared=len(common), findings=findings)


def _compare_column(name: str, b: dict, c: dict) -> list[DriftFinding]:
    out: list[DriftFinding] = []
    # DA007 dominant kind changed (ignore empty columns)
    if (b.get("kind") != c.get("kind")
            and "empty" not in (b.get("kind"), c.get("kind"))):
        out.append(DriftFinding("DA007", "high", name, {
            "from": b.get("kind"), "to": c.get("kind")}))
    # DA002 mean shift
    if "mean" in b and "mean" in c:
        base_mean = float(b["mean"])
        shift = abs(float(c["mean"]) - base_mean) / max(abs(base_mean), 1e-9)
        sev = _grade(shift, _MEAN_SHIFT)
        if sev:
            out.append(DriftFinding("DA002", sev, name, {
                "from": base_mean, "to": float(c["mean"]),
                "shift_pct": round(100 * shift, 1)}))
    # DA003 null-rate jump / DA006 unique-rate jump
    for code, key in (("DA003", "null_pct"), ("DA006", "unique_pct")):
        delta = abs(float(c.get(key, 0.0)) - float(b.get(key, 0.0)))
        sev = _grade(delta, _RATE_JUMP)
        if sev:
            out.append(DriftFinding(code, sev, name, {
                "from": b.get(key, 0.0), "to": c.get(key, 0.0),
                "delta_pp": round(delta, 1)}))
    # DA004 category share drift + DA005 appeared/vanished — categorical
    # columns only (low unique rate keeps ids/measures out)
    bs, cs = _shares(b), _shares(c)
    if bs and cs and float(b.get("unique_pct", 100.0)) <= 50.0:
        support = set(bs) | set(cs)
        l1 = sum(abs(bs.get(v, 0.0) - cs.get(v, 0.0)) for v in support)
        sev = _grade(l1, _L1_SHIFT)
        if sev:
            moved = sorted(support,
                           key=lambda v: -abs(bs.get(v, 0.0) - cs.get(v, 0.0)))
            out.append(DriftFinding("DA004", sev, name, {
                "l1": round(l1, 3),
                "moved": [{"value": v,
                           "from_pct": round(100 * bs.get(v, 0.0), 1),
                           "to_pct": round(100 * cs.get(v, 0.0), 1)}
                          for v in moved[:3]]}))
        appeared = sorted(set(cs) - set(bs))
        vanished = sorted(set(bs) - set(cs))
        if appeared or vanished:
            out.append(DriftFinding("DA005", "low", name, {
                "appeared": appeared[:5], "vanished": vanished[:5]}))
    return out
