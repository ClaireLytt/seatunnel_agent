"""Deterministic realtime-vs-offline result reconciliation.

Both sides come in as result rows (CSV with a header, or JSONL — the
sample_profile parser is reused), plus the key column(s) that identify a
row.  Rows are aligned by key and every shared numeric column is
compared under a relative tolerance: keys missing on either side, cell
diffs over the tolerance (with the worst rows), and — the caliber
smell — a systematic bias verdict per metric (realtime consistently
lower points at late data or unclosed windows; consistently higher at
duplicate consumption).  No database connection; for connected
checksum comparison use the data_comparison agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from seatunnel_agent.agents.data.sample_profile import parse_rows

__all__ = ["DiffResult", "MetricBias", "compare_results"]

_BIAS_SHARE = 0.8      # share of diffs pointing one way -> systematic


@dataclass
class MetricBias:
    column: str
    direction: str          # rt_lower / rt_higher
    median_diff_pct: float
    affected: int

    def to_dict(self) -> dict:
        return {"column": self.column, "direction": self.direction,
                "median_diff_pct": self.median_diff_pct,
                "affected": self.affected}


@dataclass
class DiffResult:
    keys: list[str]
    tolerance_pct: float
    rt_rows: int
    off_rows: int
    matched: int
    missing_in_rt: list[str] = field(default_factory=list)
    missing_in_off: list[str] = field(default_factory=list)
    mismatches: list[dict] = field(default_factory=list)
    biases: list[MetricBias] = field(default_factory=list)

    @property
    def consistent_pct(self) -> float:
        if not self.matched:
            return 0.0
        bad_keys = {m["key"] for m in self.mismatches}
        return 100.0 * (self.matched - len(bad_keys)) / self.matched

    def to_dict(self) -> dict:
        return {"keys": self.keys, "tolerance_pct": self.tolerance_pct,
                "rt_rows": self.rt_rows, "off_rows": self.off_rows,
                "matched": self.matched,
                "consistent_pct": round(self.consistent_pct, 1),
                "missing_in_rt": self.missing_in_rt[:10],
                "missing_in_rt_count": len(self.missing_in_rt),
                "missing_in_off": self.missing_in_off[:10],
                "missing_in_off_count": len(self.missing_in_off),
                "mismatches": self.mismatches[:20],
                "mismatch_count": len(self.mismatches),
                "biases": [b.to_dict() for b in self.biases]}


def _index(headers: list[str], rows: list[dict], keys: list[str],
           what: str) -> dict[tuple, dict]:
    missing = [k for k in keys if k not in headers]
    if missing:
        raise ValueError(f"{what}: key column(s) not found: "
                         f"{', '.join(missing)} / 键列不存在")
    out: dict[tuple, dict] = {}
    for row in rows:
        out[tuple(row.get(k) for k in keys)] = row
    return out


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _num(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def compare_results(realtime_text: str, offline_text: str, keys: str,
                    tolerance_pct: float = 1.0) -> DiffResult:
    key_cols = [k.strip() for k in (keys or "").split(",") if k.strip()]
    if not key_cols:
        raise ValueError("key column(s) required / 需要键列")
    rt_headers, rt_rows = parse_rows(realtime_text)
    off_headers, off_rows = parse_rows(offline_text)
    rt_idx = _index(rt_headers, rt_rows, key_cols, "realtime")
    off_idx = _index(off_headers, off_rows, key_cols, "offline")

    metric_cols = [c for c in off_headers
                   if c in rt_headers and c not in key_cols]
    result = DiffResult(keys=key_cols, tolerance_pct=tolerance_pct,
                        rt_rows=len(rt_rows), off_rows=len(off_rows),
                        matched=0)

    def _key_str(key: tuple) -> str:
        return ", ".join("∅" if v is None else str(v) for v in key)

    for key in off_idx:
        if key not in rt_idx:
            result.missing_in_rt.append(_key_str(key))
    for key in rt_idx:
        if key not in off_idx:
            result.missing_in_off.append(_key_str(key))
    result.missing_in_rt.sort()
    result.missing_in_off.sort()

    signed: dict[str, list[float]] = {c: [] for c in metric_cols}
    for key, off_row in off_idx.items():
        rt_row = rt_idx.get(key)
        if rt_row is None:
            continue
        result.matched += 1
        for col in metric_cols:
            off_v = _num(off_row.get(col))
            rt_v = _num(rt_row.get(col))
            if off_v is None or rt_v is None:
                if (off_v is None) != (rt_v is None):
                    result.mismatches.append({
                        "key": _key_str(key), "column": col,
                        "realtime": rt_row.get(col),
                        "offline": off_row.get(col), "diff_pct": None})
                continue
            diff_pct = (100.0 * (rt_v - off_v) / abs(off_v)
                        if off_v != 0 else (0.0 if rt_v == 0 else 100.0))
            if abs(diff_pct) > tolerance_pct:
                result.mismatches.append({
                    "key": _key_str(key), "column": col,
                    "realtime": rt_v, "offline": off_v,
                    "diff_pct": round(diff_pct, 2)})
                signed[col].append(diff_pct)

    result.mismatches.sort(
        key=lambda m: -(abs(m["diff_pct"]) if m["diff_pct"] is not None
                        else 1e9))

    for col, diffs in signed.items():
        if len(diffs) < 3:
            continue
        lower = sum(1 for d in diffs if d < 0)
        share = max(lower, len(diffs) - lower) / len(diffs)
        if share >= _BIAS_SHARE:
            result.biases.append(MetricBias(
                column=col,
                direction="rt_lower" if lower >= len(diffs) - lower
                else "rt_higher",
                median_diff_pct=round(_median(diffs), 2),
                affected=len(diffs)))
    return result
