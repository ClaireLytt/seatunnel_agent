"""重复建设检测 — 流水线 SQL → 同源双建/子集派生/高扇出分级发现.

Deterministic core: parse every write statement (sql_diff's statement
shapes reused), compare targets by what they read and emit — the same
source set with overlapping output expressions grades high (one table
built twice), inputs alone grade medium, a proper source subset is a
derivation candidate, and a source read by many targets flags a missing
middle layer.  No scheduler or database connection.
"""

from .detector import DupFinding, DupReport, detect_dup_pipelines
from .report import render_markdown

__all__ = [
    "DupFinding",
    "DupReport",
    "detect_dup_pipelines",
    "render_markdown",
]
