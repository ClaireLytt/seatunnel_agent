"""DDL 迁移脚本 — 新旧两版 DDL 快照 → 可执行 ALTER 迁移脚本.

Deterministic core: diff the snapshots (schema_drift reused), then emit
the migration — widenings, added columns, renames, comment updates and
new tables as runnable statements; drops, narrowing type changes and
partition-layout changes commented out with a review note so nothing
destructive runs by accident.  schema_drift reports the diff; this
ships the script.  No database connection.
"""

from .evolver import EvolvePlan, EvolveStep, build_migration
from .report import render_markdown

__all__ = [
    "EvolvePlan",
    "EvolveStep",
    "build_migration",
    "render_markdown",
]
