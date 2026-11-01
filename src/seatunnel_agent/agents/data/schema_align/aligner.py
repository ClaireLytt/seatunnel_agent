"""Deterministic source-to-sink schema alignment for sync jobs.

Input is the source table's DDL and the sink table's DDL (CREATE TABLE
with column types; MySQL/Hive/Doris spellings all parse).  Every column
is matched by name (case-insensitive) and the type mapping is judged:

* SA001 missing in sink — the column's data is silently dropped (high
  for keys, mid otherwise).
* SA002 extra NOT NULL in sink without a default — every insert fails.
* SA003 narrowing — bigint→int, decimal(38,6)→(18,2), varchar(256)→(64):
  overflow, precision loss or truncation when real data arrives.
* SA004 risky conversion — string→int/decimal/timestamp parses at run
  time and dies on the first bad row.
* SA005 temporal truncation — timestamp/datetime→date drops the time.
* SA006 nullable→NOT NULL — the first NULL kills the batch.

Widenings (int→bigint, date→timestamp, anything→string) pass silently.
No database connection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = ["AlignFinding", "AlignResult", "Column", "align_schemas",
           "parse_ddl_columns"]

_HEAD = re.compile(
    r"CREATE\s+(?:EXTERNAL\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"[`\"]?([\w.]+)[`\"]?\s*\(", re.IGNORECASE)
_COL = re.compile(r"^\s*[`\"]?(\w+)[`\"]?\s+(\w+)(?:\s*\(([^)]*)\))?(.*)$",
                  re.IGNORECASE | re.DOTALL)
_KEYWORDS = {"PRIMARY", "KEY", "CONSTRAINT", "UNIQUE", "INDEX",
             "FOREIGN", "DUPLICATE", "DISTRIBUTED", "PARTITION"}

_INT_BITS = {"tinyint": 8, "smallint": 16, "int": 32, "integer": 32,
             "bigint": 64, "largeint": 128}
_FLOATS = {"float", "double"}
_STRINGS = {"varchar", "char", "string", "text"}
_DATES = {"date"}
_TIMES = {"timestamp", "datetime"}
_KEYISH = re.compile(r"(^id$|_id$|_key$|_no$)", re.IGNORECASE)


@dataclass
class Column:
    name: str
    base: str                 # lowercase base type
    args: tuple[int, ...]     # (length,) or (precision, scale)
    not_null: bool = False
    has_default: bool = False

    def render(self) -> str:
        args = f"({','.join(str(a) for a in self.args)})" if self.args \
            else ""
        return f"{self.base}{args}" + (" NOT NULL" if self.not_null
                                       else "")


@dataclass
class AlignFinding:
    code: str          # SA001..
    severity: str      # high / mid / low
    column: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "column": self.column, "detail": self.detail}


@dataclass
class AlignResult:
    source_table: str
    sink_table: str
    matched: int
    findings: list[AlignFinding]

    def to_dict(self) -> dict:
        return {"source_table": self.source_table,
                "sink_table": self.sink_table, "matched": self.matched,
                "findings": [f.to_dict() for f in self.findings]}


def _balanced(text: str, start: int) -> str:
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
    return text[start + 1:]


def _split_top(blob: str) -> list[str]:
    parts, depth, buf = [], 0, []
    for ch in blob:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


def parse_ddl_columns(text: str, what: str) -> tuple[str, dict[str, Column]]:
    body = (text or "").strip()
    if not body:
        raise ValueError(f"{what}: empty DDL / DDL 为空")
    m = _HEAD.search(body)
    if not m:
        raise ValueError(f"{what}: no CREATE TABLE found / 没有建表语句")
    table = m.group(1)
    blob = _balanced(body, m.end() - 1)
    columns: dict[str, Column] = {}
    for line in _split_top(blob):
        cm = _COL.match(line.strip())
        if not cm or cm.group(1).upper() in _KEYWORDS:
            continue
        name, base, args_raw, rest = cm.groups()
        args: tuple[int, ...] = ()
        if args_raw:
            try:
                args = tuple(int(a.strip()) for a in args_raw.split(","))
            except ValueError:
                args = ()
        rest_up = (rest or "").upper()
        columns[name.lower()] = Column(
            name=name, base=base.lower(), args=args,
            not_null="NOT NULL" in rest_up,
            has_default="DEFAULT" in rest_up)
    if not columns:
        raise ValueError(f"{what}: no columns parsed / 没有解析出列")
    return table, columns


def _judge_types(src: Column, dst: Column) -> AlignFinding | None:
    s, d = src.base, dst.base
    col = src.name
    # identical base
    if s in _INT_BITS and d in _INT_BITS:
        if _INT_BITS[d] < _INT_BITS[s]:
            return AlignFinding("SA003", "high", col, {
                "src": src.render(), "dst": dst.render(),
                "kind": "int_narrowing"})
        return None
    if s == "decimal" and d == "decimal":
        sp = src.args or (10, 0)
        dp = dst.args or (10, 0)
        if dp[0] < sp[0] or (len(sp) > 1 and len(dp) > 1
                             and dp[1] < sp[1]):
            return AlignFinding("SA003", "high", col, {
                "src": src.render(), "dst": dst.render(),
                "kind": "precision_loss"})
        return None
    if s in _STRINGS and d in _STRINGS:
        if (src.args and dst.args and dst.args[0] < src.args[0]):
            return AlignFinding("SA003", "mid", col, {
                "src": src.render(), "dst": dst.render(),
                "kind": "truncation"})
        return None
    if s in _STRINGS and (d in _INT_BITS or d in _FLOATS
                          or d == "decimal" or d in _TIMES or d in _DATES):
        return AlignFinding("SA004", "high", col, {
            "src": src.render(), "dst": dst.render()})
    if s in _TIMES and d in _DATES:
        return AlignFinding("SA005", "mid", col, {
            "src": src.render(), "dst": dst.render()})
    if (s in _FLOATS or s == "decimal") and d in _INT_BITS:
        return AlignFinding("SA003", "high", col, {
            "src": src.render(), "dst": dst.render(),
            "kind": "fraction_loss"})
    return None


def align_schemas(source_text: str, sink_text: str) -> AlignResult:
    src_table, src_cols = parse_ddl_columns(source_text, "source")
    dst_table, dst_cols = parse_ddl_columns(sink_text, "sink")
    findings: list[AlignFinding] = []
    matched = 0

    for key, src in src_cols.items():
        dst = dst_cols.get(key)
        if dst is None:
            sev = "high" if _KEYISH.search(src.name) else "mid"
            findings.append(AlignFinding("SA001", sev, src.name, {
                "src": src.render()}))
            continue
        matched += 1
        type_f = _judge_types(src, dst)
        if type_f:
            findings.append(type_f)
        if dst.not_null and not src.not_null:
            findings.append(AlignFinding("SA006", "high", src.name, {
                "src": src.render(), "dst": dst.render()}))

    for key, dst in dst_cols.items():
        if key not in src_cols and dst.not_null and not dst.has_default:
            findings.append(AlignFinding("SA002", "high", dst.name, {
                "dst": dst.render()}))

    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code, f.column))
    return AlignResult(source_table=src_table, sink_table=dst_table,
                       matched=matched, findings=findings)
