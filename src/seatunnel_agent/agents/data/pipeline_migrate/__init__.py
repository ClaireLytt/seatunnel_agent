"""Pipeline 迁移评估 — 旧 ETL 脚本 → 目标引擎、工作量与风险.

Deterministic core: statically measure each legacy job script
(``*.sql``/``*.hql``/``*.sh``/``*.py``) — statements, joins,
UDF/TRANSFORM calls, control flow, external tools, streaming markers,
dialect-specific syntax — then suggest the target engine (SeaTunnel for
plain moves, Spark SQL for batch transforms, Flink for streaming,
scheduler for orchestration-only shells), size the effort (S/M/L) from
a transparent score, and list the constructs that will not migrate
mechanically.  Nothing is executed.
"""

from .assessor import (
    JobAssessment,
    MigrationReport,
    assess_dir,
    assess_job,
    assess_text,
)
from .report import render_markdown

__all__ = [
    "JobAssessment",
    "MigrationReport",
    "assess_dir",
    "assess_job",
    "assess_text",
    "render_markdown",
]
