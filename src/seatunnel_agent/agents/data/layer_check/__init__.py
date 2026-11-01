"""数仓分层体检 — SQL 血缘 × 分层拓扑 → 违规清单与整改处方.

Deterministic core: build the lineage from pasted SQL (data_lineage
parser via the quality_trace helper), rank every table's layer from its
name prefix (built-in or custom map), and judge every edge — layer
skips, reverse dependencies, same-layer chaining in the aggregate
layers, unknown-layer names.  No database connection.
"""

from .checker import (
    LayerFinding,
    LayerResult,
    check_layers,
    parse_layer_map,
    run_layer_check,
)
from .report import render_markdown

__all__ = [
    "LayerFinding",
    "LayerResult",
    "check_layers",
    "parse_layer_map",
    "render_markdown",
    "run_layer_check",
]
