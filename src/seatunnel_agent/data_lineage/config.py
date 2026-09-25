"""Configuration for the data lineage agent (env-driven)."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_META_TABLE = "zz.dwm_meta_table_lineage_df"

# Single source of truth for lineage limits — the graph/render hard caps and
# the LineageConfig defaults must never drift apart.
DEFAULT_DEPTH = 3
MAX_DEPTH = 10
MAX_NODES = 200
MAX_MERMAID_NODES = 80
COLUMN_IMPACT_DEPTH = 5

DIRECTIONS = ("upstream", "downstream", "both")


@dataclass(frozen=True)
class LineageConfig:
    meta_table: str = DEFAULT_META_TABLE
    default_depth: int = DEFAULT_DEPTH
    max_depth: int = MAX_DEPTH
    max_nodes: int = MAX_NODES
    max_mermaid_nodes: int = MAX_MERMAID_NODES


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def load_lineage_config() -> LineageConfig:
    return LineageConfig(
        meta_table=os.getenv("LINEAGE_META_TABLE", DEFAULT_META_TABLE).strip()
        or DEFAULT_META_TABLE,
        default_depth=_int_env("LINEAGE_DEFAULT_DEPTH", DEFAULT_DEPTH),
        max_depth=_int_env("LINEAGE_MAX_DEPTH", MAX_DEPTH),
        max_nodes=_int_env("LINEAGE_MAX_NODES", MAX_NODES),
        max_mermaid_nodes=_int_env("LINEAGE_MAX_MERMAID_NODES", MAX_MERMAID_NODES),
    )
