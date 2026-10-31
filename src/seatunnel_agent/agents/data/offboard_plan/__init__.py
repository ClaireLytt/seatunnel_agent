"""下线方案 — 要下线的表 × 血缘 → 公示/冻结/归档/删除四阶段编排.

Deterministic core: walk the lineage DOWNSTREAM of the table
(quality_trace's builder reused) — live consumers block the plan and
are named for migration — then stage announce, freeze (deprecated mark,
producer pause), archive (snapshot + row-count verify) and a DROP that
stays commented until the archive verifies (ddl_evolve's discipline).
field_usage finds the candidates; this ships the plan.  No scheduler or
database connection.
"""

from .planner import OffboardPlan, OffboardStep, plan_offboard
from .report import render_markdown

__all__ = [
    "OffboardPlan",
    "OffboardStep",
    "plan_offboard",
    "render_markdown",
]
