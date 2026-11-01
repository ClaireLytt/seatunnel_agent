"""Deterministic semantic diff between two job configurations.

Both sides parse through pyhocon (the config_lint parser's stack), so
SeaTunnel HOCON, JSON and flat ``key = value`` properties all work;
comments, ordering and formatting never count as differences.  The
nested config flattens to dotted keys, and every added / removed /
changed key is graded by what it controls:

* high — keys steering throughput, state or the data's destination
  (parallelism, memory, checkpoint, table/topic/url/database/path,
  partition, mode, format);
* mid — tuning knobs (batch, buffer, retry, timeout, interval, rate);
* low — everything else.

Values of secret-shaped keys (password/secret/token/key) are masked in
the output; a changed secret is still reported, just not printed.  No
environment connection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = ["ConfigDiffResult", "DiffEntry", "diff_configs",
           "flatten_config", "parse_config"]

_HIGH = re.compile(r"(parallelism|memory|checkpoint|savepoint|"
                   r"table|topic|url|database|path|partition|mode|format|"
                   r"server-?id|group\.?id)", re.IGNORECASE)
_MID = re.compile(r"(batch|buffer|retr|timeout|interval|rate|size|"
                  r"fetch|poll|commit)", re.IGNORECASE)
_SECRET = re.compile(r"(password|secret|token|access.?key|passwd)",
                     re.IGNORECASE)


@dataclass
class DiffEntry:
    key: str
    kind: str          # added / removed / changed
    severity: str      # high / mid / low
    old: str | None = None
    new: str | None = None

    def to_dict(self) -> dict:
        return {"key": self.key, "kind": self.kind,
                "severity": self.severity, "old": self.old,
                "new": self.new}


@dataclass
class ConfigDiffResult:
    left_keys: int
    right_keys: int
    entries: list[DiffEntry] = field(default_factory=list)

    @property
    def identical(self) -> bool:
        return not self.entries

    def to_dict(self) -> dict:
        return {"left_keys": self.left_keys,
                "right_keys": self.right_keys,
                "identical": self.identical,
                "entries": [e.to_dict() for e in self.entries]}


def parse_config(text: str, what: str) -> dict:
    body = (text or "").strip()
    if not body:
        raise ValueError(f"{what}: empty config / 配置为空")
    from pyhocon import ConfigFactory

    try:
        return ConfigFactory.parse_string(body).as_plain_ordered_dict()
    except Exception as exc:
        raise ValueError(f"{what}: cannot parse ({str(exc)[:160]})") from exc


def flatten_config(node, prefix: str = "") -> dict[str, str]:
    """Nested dict/list → {dotted.key: rendered value}."""
    flat: dict[str, str] = {}
    if isinstance(node, dict):
        for k, v in node.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            flat.update(flatten_config(v, key))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            flat.update(flatten_config(v, f"{prefix}[{i}]"))
    else:
        flat[prefix] = "null" if node is None else str(node)
    return flat


def _severity(key: str) -> str:
    if _HIGH.search(key):
        return "high"
    if _MID.search(key):
        return "mid"
    return "low"


def _render(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    if _SECRET.search(key):
        return "***"
    return value if len(value) <= 120 else value[:117] + "..."


def diff_configs(left_text: str, right_text: str) -> ConfigDiffResult:
    left = flatten_config(parse_config(left_text, "left"))
    right = flatten_config(parse_config(right_text, "right"))
    entries: list[DiffEntry] = []
    for key in sorted(set(left) | set(right)):
        in_l, in_r = key in left, key in right
        if in_l and not in_r:
            entries.append(DiffEntry(key=key, kind="removed",
                                     severity=_severity(key),
                                     old=_render(key, left[key])))
        elif in_r and not in_l:
            entries.append(DiffEntry(key=key, kind="added",
                                     severity=_severity(key),
                                     new=_render(key, right[key])))
        elif left[key] != right[key]:
            entries.append(DiffEntry(key=key, kind="changed",
                                     severity=_severity(key),
                                     old=_render(key, left[key]),
                                     new=_render(key, right[key])))
    order = {"high": 0, "mid": 1, "low": 2}
    kind_order = {"changed": 0, "removed": 1, "added": 2}
    entries.sort(key=lambda e: (order[e.severity], kind_order[e.kind],
                                e.key))
    return ConfigDiffResult(left_keys=len(left), right_keys=len(right),
                            entries=entries)
