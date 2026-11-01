"""调度文件生成 — 流水线 SQL → 可 import 的 Airflow dag.py 骨架.

Deterministic core: parse the write statements (sql_diff's statement
shapes reused), make one task per write target, wire edges where a
target reads another, and flag external upstream tables where sensors
belong — rendered as an Airflow DAG skeleton that passes ``ast.parse``.
dag_check diagnoses the graph; this ships the scheduler file.  No
scheduler connection.
"""

from .generator import DagDraft, TaskSpec, generate_dag
from .report import render_markdown

__all__ = [
    "DagDraft",
    "TaskSpec",
    "generate_dag",
    "render_markdown",
]
