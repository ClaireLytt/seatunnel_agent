"""Structured lineage analysis report."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .graph import ChainResult, ColumnImpactResult, TableNode


def sla_nodes_of(chain: ChainResult) -> list[TableNode]:
    return [n for _, n in sorted(chain.nodes.items()) if n.is_sla]


def baseline_nodes_of(chain: ChainResult) -> list[TableNode]:
    return [n for _, n in sorted(chain.nodes.items()) if n.baselines]


@dataclass
class LineageReport:
    root_table: str
    direction: str = "both"
    chain: ChainResult | None = None
    column_impact: ColumnImpactResult | None = None
    sla_nodes: list[TableNode] = field(default_factory=list)
    baseline_nodes: list[TableNode] = field(default_factory=list)
    summary: str = ""
    mermaid: str = ""

    def __post_init__(self) -> None:
        if self.chain and not self.sla_nodes:
            self.sla_nodes = sla_nodes_of(self.chain)
        if self.chain and not self.baseline_nodes:
            self.baseline_nodes = baseline_nodes_of(self.chain)

    def stats(self) -> dict[str, int]:
        if not self.chain:
            return {"upstream": 0, "downstream": 0, "edges": 0}
        return {
            "upstream": self.chain.upstream_count,
            "downstream": self.chain.downstream_count,
            "edges": len(self.chain.edges),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_table": self.root_table,
            "direction": self.direction,
            "chain": self.chain.to_dict() if self.chain else None,
            "column_impact": self.column_impact.to_dict() if self.column_impact else None,
            "sla_nodes": [n.to_dict() for n in self.sla_nodes],
            "baseline_nodes": [n.to_dict() for n in self.baseline_nodes],
            "summary": self.summary,
            "mermaid": self.mermaid,
            "stats": self.stats(),
        }
