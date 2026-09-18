"""Configuration for the data lineage agent (env-driven)."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_META_TABLE = "zz.dwm_meta_table_lineage_df"


@dataclass(frozen=True)
class LineageConfig:
    meta_table: str = DEFAULT_META_TABLE
    default_depth: int = 3
    max_depth: int = 10
    max_nodes: int = 200
    max_mermaid_nodes: int = 80


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
        default_depth=_int_env("LINEAGE_DEFAULT_DEPTH", 3),
        max_depth=_int_env("LINEAGE_MAX_DEPTH", 10),
        max_nodes=_int_env("LINEAGE_MAX_NODES", 200),
        max_mermaid_nodes=_int_env("LINEAGE_MAX_MERMAID_NODES", 80),
    )
