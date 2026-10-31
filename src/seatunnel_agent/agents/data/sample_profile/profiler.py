"""Deterministic sampling + per-column profiling over raw data rows.

Input is CSV (header row) or JSONL text.  A reproducible stride sample
caps the working rows, then every column gets a profile — inferred type,
null/unique rates, numeric range, top categories, format buckets — and
rule findings flag the suspicious ones (mixed types, outlier formats,
numeric-as-text, constants, whitespace/case drift).  Stdlib only, no
database connection, same input twice → same report twice.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field

__all__ = [
    "ColumnProfile",
    "Finding",
    "ProfileResult",
    "parse_rows",
    "profile_rows",
    "sample_rows",
]

_NULL_TOKENS = {"", "null", "none", "nan", "n/a", "na", "\\n"}

# format buckets, first match wins (most specific first)
_FORMATS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("uuid", re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")),
    ("datetime", re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?")),
    ("date", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("date_slash", re.compile(r"^\d{1,4}/\d{1,2}/\d{1,4}$")),
    ("email", re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")),
    ("phone", re.compile(r"^\+?\d[\d\- ]{6,18}\d$")),
    ("integer", re.compile(r"^-?\d+$")),
    ("decimal", re.compile(r"^-?\d+\.\d+$")),
    ("bool", re.compile(r"^(true|false|yes|no|0|1)$", re.IGNORECASE)),
)
_TEXT_BUCKET = "text"


def _bucket(value: str) -> str:
    for name, pat in _FORMATS:
        if pat.match(value):
            return name
    return _TEXT_BUCKET

_NUMERIC_BUCKETS = {"integer", "decimal"}
_TEMPORAL_BUCKETS = {"date", "datetime", "date_slash"}


@dataclass
class Finding:
    code: str          # SP001..
    severity: str      # high / mid / low
    column: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "column": self.column, "detail": self.detail}


@dataclass
class ColumnProfile:
    name: str
    kind: str                     # dominant bucket or 'mixed'/'empty'
    non_null: int = 0
    null_pct: float = 0.0
    unique_pct: float = 0.0
    buckets: dict[str, int] = field(default_factory=dict)
    top: list[tuple[str, int]] = field(default_factory=list)
    vmin: float | None = None
    vmax: float | None = None
    mean: float | None = None
    examples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {"name": self.name, "kind": self.kind, "non_null": self.non_null,
             "null_pct": round(self.null_pct, 2),
             "unique_pct": round(self.unique_pct, 2),
             "buckets": self.buckets,
             "top": [{"value": v, "count": c} for v, c in self.top]}
        if self.vmin is not None:
            d.update(min=self.vmin, max=self.vmax,
                     mean=round(self.mean or 0.0, 4))
        return d


@dataclass
class ProfileResult:
    total_rows: int
    sampled_rows: int
    columns: list[ColumnProfile]
    findings: list[Finding]

    def to_dict(self) -> dict:
        return {"total_rows": self.total_rows,
                "sampled_rows": self.sampled_rows,
                "columns": [c.to_dict() for c in self.columns],
                "findings": [f.to_dict() for f in self.findings]}


def parse_rows(text: str) -> tuple[list[str], list[dict[str, str | None]]]:
    """CSV (header row) or JSONL → (ordered headers, rows of str|None)."""
    body = (text or "").strip()
    if not body:
        raise ValueError("empty input / 输入为空")
    first = body.lstrip()[:1]
    if first in "{[":
        return _parse_jsonl(body)
    reader = csv.reader(io.StringIO(body))
    table = [row for row in reader if any(cell.strip() for cell in row)]
    if len(table) < 2:
        raise ValueError("CSV needs a header row plus data rows / "
                         "CSV 需要表头行 + 数据行")
    headers = [h.strip() for h in table[0]]
    rows: list[dict[str, str | None]] = []
    for raw in table[1:]:
        row: dict[str, str | None] = {}
        for i, h in enumerate(headers):
            cell = raw[i] if i < len(raw) else ""
            row[h] = None if cell.strip().lower() in _NULL_TOKENS else cell
        rows.append(row)
    return headers, rows


def _parse_jsonl(body: str) -> tuple[list[str], list[dict[str, str | None]]]:
    lines = [ln for ln in body.splitlines() if ln.strip()]
    if lines[0].lstrip().startswith("["):      # a JSON array also works
        items = json.loads(body)
        if not isinstance(items, list):
            raise ValueError("JSON must be an array of objects")
    else:
        items = [json.loads(ln) for ln in lines]
    headers: list[str] = []
    rows: list[dict[str, str | None]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each JSONL line must be an object / "
                             "JSONL 每行须是对象")
        for k in item:
            if k not in headers:
                headers.append(k)
        row: dict[str, str | None] = {}
        for k, v in item.items():
            if v is None:
                row[k] = None
            elif isinstance(v, bool):
                row[k] = "true" if v else "false"
            elif isinstance(v, (int, float)):
                row[k] = f"{v:g}"
            else:
                s = str(v)
                row[k] = None if s.strip().lower() in _NULL_TOKENS else s
        rows.append(row)
    if not rows:
        raise ValueError("no data rows / 没有数据行")
    return headers, rows


def sample_rows(rows: list[dict[str, str | None]],
                max_rows: int = 2000) -> list[dict[str, str | None]]:
    """Reproducible stride sample: every k-th row, first row kept."""
    if max_rows <= 0 or len(rows) <= max_rows:
        return rows
    stride = len(rows) / max_rows
    return [rows[int(i * stride)] for i in range(max_rows)]


def profile_rows(headers: list[str], rows: list[dict[str, str | None]],
                 total_rows: int | None = None) -> ProfileResult:
    total = total_rows if total_rows is not None else len(rows)
    columns = [_profile_column(h, rows) for h in headers]
    findings = _find_issues(columns, rows)
    return ProfileResult(total_rows=total, sampled_rows=len(rows),
                         columns=columns, findings=findings)


def _profile_column(name: str,
                    rows: list[dict[str, str | None]]) -> ColumnProfile:
    values = [row.get(name) for row in rows]
    present = [v for v in values if v is not None]
    n = len(values) or 1
    prof = ColumnProfile(
        name=name, kind="empty", non_null=len(present),
        null_pct=100.0 * (len(values) - len(present)) / n)
    if not present:
        return prof
    counts: dict[str, int] = {}
    buckets: dict[str, int] = {}
    for v in present:
        counts[v] = counts.get(v, 0) + 1
        b = _bucket(v.strip())
        buckets[b] = buckets.get(b, 0) + 1
    prof.unique_pct = 100.0 * len(counts) / len(present)
    prof.buckets = dict(sorted(buckets.items(),
                               key=lambda kv: (-kv[1], kv[0])))
    dominant, dom_n = next(iter(prof.buckets.items()))
    prof.kind = dominant if dom_n == len(present) else (
        dominant if dom_n / len(present) >= 0.9 else "mixed")
    prof.top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    nums = []
    for v in present:
        s = v.strip()
        if _bucket(s) in _NUMERIC_BUCKETS:
            nums.append(float(s))
    if nums and len(nums) / len(present) >= 0.5:
        prof.vmin, prof.vmax = min(nums), max(nums)
        prof.mean = sum(nums) / len(nums)
    seen: list[str] = []
    for v in present:
        if v not in seen:
            seen.append(v)
        if len(seen) == 3:
            break
    prof.examples = seen
    return prof


def _find_issues(columns: list[ColumnProfile],
                 rows: list[dict[str, str | None]]) -> list[Finding]:
    findings: list[Finding] = []
    for c in columns:
        if c.non_null == 0:
            findings.append(Finding("SP003", "mid", c.name,
                                    {"reason": "all_null"}))
            continue
        # SP001 mixed types: no bucket reaches 90%
        dominant, dom_n = next(iter(c.buckets.items()))
        dom_pct = 100.0 * dom_n / c.non_null
        if dom_pct < 90.0 and len(c.buckets) > 1:
            findings.append(Finding("SP001", "high", c.name, {
                "buckets": c.buckets, "dominant": dominant,
                "dominant_pct": round(dom_pct, 1)}))
        # SP004 outlier formats: dominant >=90% but stragglers exist
        elif len(c.buckets) > 1:
            minority = {b: n for b, n in c.buckets.items() if b != dominant}
            offenders = _offenders(c.name, rows, dominant)
            findings.append(Finding("SP004", "mid", c.name, {
                "dominant": dominant, "minority": minority,
                "examples": offenders[:3]}))
        # SP002 high null rate
        if c.null_pct >= 50.0:
            findings.append(Finding("SP002", "mid", c.name,
                                    {"null_pct": round(c.null_pct, 1)}))
        # SP003 constant column
        if c.non_null > 1 and len(c.top) == 1:
            findings.append(Finding("SP003", "low", c.name,
                                    {"value": c.top[0][0]}))
        # SP005 numeric stored as text with grouping/currency noise
        if c.kind == _TEXT_BUCKET:
            noisy = [v for v, _ in c.top
                     if re.fullmatch(r"[-+]?[\d,，]+(\.\d+)?%?|[¥$€]\s?[\d.,]+",
                                     v.strip())]
            if noisy:
                findings.append(Finding("SP005", "mid", c.name,
                                        {"examples": noisy[:3]}))
        # SP006 whitespace / case drift: same value after normalization
        norm: dict[str, set[str]] = {}
        for v, _ in c.top:
            norm.setdefault(v.strip().lower(), set()).add(v)
        drift = {k: sorted(vs) for k, vs in norm.items() if len(vs) > 1}
        if drift:
            findings.append(Finding("SP006", "low", c.name,
                                    {"variants": drift}))
    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code, f.column))
    return findings


def _offenders(name: str, rows: list[dict[str, str | None]],
               dominant: str) -> list[dict]:
    out = []
    for i, row in enumerate(rows, start=1):
        v = row.get(name)
        if v is not None and _bucket(v.strip()) != dominant:
            out.append({"row": i, "value": v})
            if len(out) == 5:
                break
    return out
