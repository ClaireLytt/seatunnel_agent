"""Freshness verdicts over a table-update inventory.

Input model: update events — ``table`` plus ``updated`` (ISO timestamp),
one event per produced batch/partition. JSON is a list of such objects
(synonyms accepted: name/dataset for table, updated_at/time/ts/partition
for updated) or a ``{"tables": [{"table", "updates": [...]}]}`` wrapper;
CSV uses ``table,updated`` columns.

Optional rules (JSON object, fnmatch patterns over table names)::

    {"ods.*": {"interval": "1d", "max_age": "26h"}}

Verdict per table, evaluated at *now* (default: the latest update seen
anywhere in the inventory, so runs are reproducible):

* **stalled** — no update for ``stall_factor`` x interval (data stopped),
* **stale**   — age of the latest update exceeds the rule's ``max_age``,
* **late**    — the latest update arrived more than ``grace`` x interval
  after the previous one (produced, but behind schedule),
* **ok** otherwise.

The expected interval comes from the rule, or is inferred as the median
gap between updates (needs >= 3 updates); tables with neither get an
``unknown`` verdict instead of a guess.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatch
from statistics import median
from typing import Any

MAX_EVENTS = 200_000
STALL_FACTOR = 2.0     # no update for 2x interval -> stalled
GRACE_FACTOR = 1.25    # last gap beyond 1.25x interval -> late

_TABLE_KEYS = ("table", "name", "dataset", "table_name")
_UPDATED_KEYS = ("updated", "updated_at", "time", "ts", "partition",
                 "batch", "end", "end_time")

_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([dhms])", re.IGNORECASE)
_DURATION_S = {"d": 86400.0, "h": 3600.0, "m": 60.0, "s": 1.0}

#: verdicts ordered by severity, worst first
SEVERITY = ("stalled", "stale", "late", "unknown", "ok")


@dataclass
class TableFreshness:
    table: str
    updates: list[datetime]                 # sorted ascending
    interval_s: float | None = None         # expected cadence
    interval_src: str = ""                  # "rule" | "inferred" | ""
    max_age_s: float | None = None          # from the rule, if any
    verdict: str = "ok"
    age_s: float = 0.0                      # now - last update
    detail: str = ""                        # machine-readable reason key

    @property
    def last_updated(self) -> datetime:
        return self.updates[-1]

    @property
    def last_gap_s(self) -> float | None:
        if len(self.updates) < 2:
            return None
        return (self.updates[-1] - self.updates[-2]).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "updates": len(self.updates),
            "last_updated": self.last_updated.isoformat(sep=" "),
            "age_s": round(self.age_s, 1),
            "interval_s": (round(self.interval_s, 1)
                           if self.interval_s else None),
            "interval_src": self.interval_src,
            "max_age_s": (round(self.max_age_s, 1)
                          if self.max_age_s else None),
            "verdict": self.verdict,
            "detail": self.detail,
        }


@dataclass
class FreshnessScan:
    now: datetime
    tables: list[TableFreshness] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def count(self, verdict: str) -> int:
        return sum(1 for t in self.tables if t.verdict == verdict)

    def worst(self) -> str:
        """The most severe verdict present ('ok' when all is well)."""
        for v in SEVERITY:
            if v != "ok" and self.count(v):
                return v
        return "ok"


def parse_duration(text: str) -> float:
    """'1d', '26h', '90m', '1h30m' -> seconds."""
    matches = _DURATION_RE.findall(text or "")
    if not matches or _DURATION_RE.sub("", text).strip():
        raise ValueError(f"无法解析时长: {text!r}（支持 1d / 26h / 90m / 30s）")
    return sum(float(n) * _DURATION_S[u.lower()] for n, u in matches)


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def _parse_ts(value: Any, what: str) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", ""))
    except ValueError as exc:
        raise ValueError(f"无法解析时间 {what}={value!r}: {exc}") from exc


def parse_events(text: str) -> dict[str, list[datetime]]:
    """Update events per table from JSON or CSV text, sorted ascending."""
    stripped = text.strip()
    if not stripped:
        raise ValueError("输入为空")
    rows: list[dict[str, Any]] = []
    if stripped[0] in "[{":
        data = json.loads(stripped)
        if isinstance(data, dict):     # {"tables": [...]} wrapper
            for key in ("tables", "events", "updates", "data"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            raise ValueError("JSON 必须是更新事件数组（或含 tables 数组的对象）")
        for item in data:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("updates"), list):   # grouped form
                name = _pick(item, _TABLE_KEYS)
                for ts in item["updates"]:
                    rows.append({"table": name, "updated": ts})
            else:
                rows.append(item)
    else:
        rows = list(csv.DictReader(io.StringIO(stripped)))
    if len(rows) > MAX_EVENTS:
        raise ValueError(f"更新事件超过上限 {MAX_EVENTS}")

    out: dict[str, list[datetime]] = {}
    for i, row in enumerate(rows, start=1):
        name = _pick(row, _TABLE_KEYS)
        if not name:
            raise ValueError(f"第 {i} 条记录缺少表名（table/name/dataset）")
        ts = _pick(row, _UPDATED_KEYS)
        if ts is None:
            raise ValueError(f"表 {name} 的第 {i} 条记录缺少更新时间")
        out.setdefault(str(name).strip(), []).append(_parse_ts(ts, "updated"))
    for updates in out.values():
        updates.sort()
    return out


def parse_rules(text: str) -> dict[str, dict[str, float]]:
    """Rules JSON -> {pattern: {interval_s?, max_age_s?}} in seconds."""
    stripped = (text or "").strip()
    if not stripped:
        return {}
    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise ValueError("规则必须是 JSON 对象: {表名通配: {interval, max_age}}")
    out: dict[str, dict[str, float]] = {}
    for pattern, rule in data.items():
        if not isinstance(rule, dict):
            raise ValueError(f"规则 {pattern} 必须是对象")
        parsed: dict[str, float] = {}
        if rule.get("interval"):
            parsed["interval_s"] = parse_duration(str(rule["interval"]))
        if rule.get("max_age"):
            parsed["max_age_s"] = parse_duration(str(rule["max_age"]))
        out[str(pattern)] = parsed
    return out


def _match_rule(table: str,
                rules: dict[str, dict[str, float]]) -> dict[str, float]:
    for pattern, rule in rules.items():
        if table == pattern or fnmatch(table, pattern):
            return rule
    return {}


def _infer_interval(updates: list[datetime]) -> float | None:
    if len(updates) < 3:
        return None
    gaps = [(b - a).total_seconds()
            for a, b in zip(updates, updates[1:]) if b > a]
    return median(gaps) if gaps else None


def scan(events: dict[str, list[datetime]],
         rules: dict[str, dict[str, float]] | None = None,
         now: str | None = None) -> FreshnessScan:
    """Freshness verdict per table at *now* (default: latest update seen)."""
    if not events:
        raise ValueError("没有更新事件")
    rules = rules or {}
    if now:
        at = _parse_ts(now, "now")
    else:
        at = max(u[-1] for u in events.values())
    result = FreshnessScan(now=at)

    for table in sorted(events):
        updates = events[table]
        tf = TableFreshness(table=table, updates=updates)
        tf.age_s = (at - tf.last_updated).total_seconds()
        rule = _match_rule(table, rules)
        tf.max_age_s = rule.get("max_age_s")
        if "interval_s" in rule:
            tf.interval_s, tf.interval_src = rule["interval_s"], "rule"
        else:
            inferred = _infer_interval(updates)
            if inferred:
                tf.interval_s, tf.interval_src = inferred, "inferred"

        if tf.interval_s and tf.age_s > STALL_FACTOR * tf.interval_s:
            tf.verdict, tf.detail = "stalled", "no_update"
        elif tf.max_age_s is not None and tf.age_s > tf.max_age_s:
            tf.verdict, tf.detail = "stale", "over_max_age"
        elif (tf.interval_s and tf.last_gap_s is not None
                and tf.last_gap_s > GRACE_FACTOR * tf.interval_s):
            tf.verdict, tf.detail = "late", "gap_over_interval"
        elif tf.interval_s is None and tf.max_age_s is None:
            tf.verdict, tf.detail = "unknown", "no_cadence"
        result.tables.append(tf)

    result.tables.sort(key=lambda t: (SEVERITY.index(t.verdict), -t.age_s))
    unknown = result.count("unknown")
    if unknown:
        result.warnings.append(
            f"{unknown} 张表更新次数不足且无规则，无法判定节奏（unknown）")
    return result
