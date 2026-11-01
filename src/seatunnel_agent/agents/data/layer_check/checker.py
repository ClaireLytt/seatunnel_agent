"""Deterministic warehouse-layering conformance check over SQL lineage.

The lineage graph comes from the data_lineage parser (reused via the
quality_trace helper pattern); every table gets a layer from its name —
the schema part of a dotted name, or the prefix before the first
underscore otherwise — against a rank map (built-in: ods=0, stg=0,
dwd=1, dim=1, dws=2, ads=3, tmp ignored; a custom JSON map replaces
it).  Every lineage edge is then judged against the topology:

* LC002 reverse dependency — a lower layer reading a higher one
  (dwd reading dws): the layering inverted, always high.
* LC001 layer skip — a read jumping 2+ ranks (ods straight into dws is
  mid; straight into ads is high): the modeling layer was bypassed.
* LC003 same-layer chaining in the aggregate layers (dws reading dws,
  ads reading ads): aggregates stacked on aggregates, low.
* LC004 unknown layer — a table whose name maps to no rank: the
  convention cannot be checked, listed for naming cleanup.

No database connection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from seatunnel_agent.agents.data.quality_trace import build_graph_from_sql

__all__ = ["LayerFinding", "LayerResult", "check_layers",
           "parse_layer_map", "run_layer_check"]

_DEFAULT_LAYERS: dict[str, int] = {
    "ods": 0, "stg": 0, "src": 0,
    "dwd": 1, "dim": 1,
    "dws": 2, "dwm": 2,
    "ads": 3, "rpt": 3, "app": 3,
}
_IGNORED = {"tmp", "temp", "bak"}

_CHAIN_LAYERS = {2, 3}      # aggregate ranks where same-layer reads smell


@dataclass
class LayerFinding:
    code: str          # LC001..
    severity: str      # high / mid / low
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail}


@dataclass
class LayerResult:
    tables: int
    edges: int
    layer_counts: dict[str, int]
    findings: list[LayerFinding]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"tables": self.tables, "edges": self.edges,
                "layer_counts": self.layer_counts,
                "findings": [f.to_dict() for f in self.findings],
                "warnings": self.warnings}


def parse_layer_map(text: str) -> dict[str, int]:
    """Custom layer map: JSON {"prefix": rank}; replaces the built-in."""
    body = (text or "").strip()
    if not body:
        raise ValueError("empty layer map / 分层表为空")
    try:
        raw = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"layer map must be JSON: {exc}") from exc
    if not isinstance(raw, dict) or not raw:
        raise ValueError("layer map needs {prefix: rank} entries")
    try:
        return {str(k).strip().lower(): int(v) for k, v in raw.items()}
    except (TypeError, ValueError) as exc:
        raise ValueError(f"layer ranks must be integers: {exc}") from exc


def _prefix_of(table: str) -> str:
    name = table.strip().lower()
    if "." in name:
        return name.split(".", 1)[0]
    return name.split("_", 1)[0]


def check_layers(graph, warnings: list[str],
                 layers: dict[str, int] | None = None) -> LayerResult:
    ranks = layers or _DEFAULT_LAYERS
    findings: list[LayerFinding] = []
    layer_counts: dict[str, int] = {}
    unknown: list[str] = []

    rank_of: dict[str, int | None] = {}
    for name in graph.nodes:
        prefix = _prefix_of(name)
        if prefix in _IGNORED:
            rank_of[name] = None
            layer_counts[prefix] = layer_counts.get(prefix, 0) + 1
            continue
        rank = ranks.get(prefix)
        rank_of[name] = rank
        layer_counts[prefix] = layer_counts.get(prefix, 0) + 1
        if rank is None:
            unknown.append(name)
    if unknown:
        findings.append(LayerFinding("LC004", "low", {
            "count": len(unknown), "tables": sorted(unknown)[:8]}))

    edges = sorted({(src, dst) for dst, ups in graph.upstream.items()
                    for src in ups})
    for src, dst in edges:
        sr, dr = rank_of.get(src), rank_of.get(dst)
        if sr is None or dr is None:
            continue
        if sr > dr:
            findings.append(LayerFinding("LC002", "high", {
                "src": src, "dst": dst,
                "src_layer": _prefix_of(src), "dst_layer": _prefix_of(dst)}))
        elif dr - sr >= 2:
            findings.append(LayerFinding(
                "LC001", "high" if dr - sr >= 3 else "mid", {
                    "src": src, "dst": dst, "skipped": dr - sr - 1,
                    "src_layer": _prefix_of(src),
                    "dst_layer": _prefix_of(dst)}))
        elif sr == dr and sr in _CHAIN_LAYERS and src != dst:
            findings.append(LayerFinding("LC003", "low", {
                "src": src, "dst": dst, "layer": _prefix_of(dst)}))

    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code,
                                 str(f.detail.get("dst", ""))))
    return LayerResult(tables=len(graph.nodes), edges=len(edges),
                       layer_counts=dict(sorted(layer_counts.items())),
                       findings=findings, warnings=list(warnings))


def run_layer_check(sql_text: str, dialect: str = "hive",
                    layers: dict[str, int] | None = None) -> LayerResult:
    graph, warnings = build_graph_from_sql(sql_text, dialect=dialect)
    return check_layers(graph, warnings, layers=layers)
