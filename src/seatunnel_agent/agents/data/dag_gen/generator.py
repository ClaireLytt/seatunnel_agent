"""Deterministic Airflow-DAG draft generation from pipeline SQL.

dag_check diagnoses a dependency graph; this agent ships the scheduler
file.  Paste the pipeline SQL (sql_diff's statement shapes reused):
every write target becomes a task, the dependency edges come from which
targets read which, external source tables surface as wait-sensor
placeholders, and the output is a runnable Airflow DAG skeleton —
one BashOperator per task with a ``<RUN {table}>`` placeholder command,
``task_id`` sanitized from the table name, edges wired with ``>>``.
The draft is parsed with ``ast.parse`` before it is returned, so the
file always imports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = ["DagDraft", "TaskSpec", "generate_dag"]

_IDENT = re.compile(r"[^0-9A-Za-z_]+")


def _task_id(table: str) -> str:
    return _IDENT.sub("_", table).strip("_").lower()


@dataclass
class TaskSpec:
    table: str
    task_id: str
    upstream: list[str] = field(default_factory=list)   # task_ids
    external: list[str] = field(default_factory=list)   # source tables

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "task_id": self.task_id,
                "upstream": list(self.upstream),
                "external": list(self.external)}


@dataclass
class DagDraft:
    dag_id: str
    schedule: str
    tasks: list[TaskSpec] = field(default_factory=list)
    externals: list[str] = field(default_factory=list)  # all external tables
    edges: int = 0
    python_text: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"dag_id": self.dag_id, "schedule": self.schedule,
                "tasks_total": len(self.tasks),
                "edges": self.edges,
                "externals": list(self.externals),
                "tasks": [t.to_dict() for t in self.tasks],
                "python_text": self.python_text,
                "warnings": list(self.warnings)}


def _render(draft: DagDraft) -> str:
    lines = [
        '"""Auto-drafted Airflow DAG — replace every <RUN ...> placeholder',
        "with the real submit command before deploying.",
        '"""',
        "",
        "from datetime import datetime",
        "",
        "from airflow import DAG",
        "from airflow.operators.bash import BashOperator",
        "",
        "with DAG(",
        f'    dag_id="{draft.dag_id}",',
        f'    schedule="{draft.schedule}",',
        "    start_date=datetime(2026, 1, 1),",
        "    catchup=False,",
        '    tags=["drafted"],',
        ") as dag:",
    ]
    for t in draft.tasks:
        if t.external:
            ext = ", ".join(t.external)
            lines.append(f"    # upstream outside this script: {ext} — "
                         "add sensors if another DAG produces them")
        lines += [
            f"    {t.task_id} = BashOperator(",
            f'        task_id="{t.task_id}",',
            f'        bash_command="echo <RUN {t.table}>",',
            "    )",
        ]
    edge_lines = []
    for t in draft.tasks:
        for up in t.upstream:
            edge_lines.append(f"    {up} >> {t.task_id}")
    if edge_lines:
        lines.append("")
        lines += edge_lines
    return "\n".join(lines) + "\n"


def generate_dag(sql_text: str, dag_id: str = "pipeline",
                 schedule: str = "0 2 * * *",
                 dialect: str = "hive") -> DagDraft:
    """Pipeline SQL → importable Airflow DAG skeleton."""
    import ast

    from seatunnel_agent.agents.data.sql_diff.differ import statement_shapes

    if not (dag_id or "").strip() or _IDENT.search(dag_id):
        raise ValueError("dag_id must be a plain identifier "
                         "(letters, digits, underscores)")
    shapes, warnings = statement_shapes(sql_text, dialect)
    targets = {s.target: s for s in shapes
               if not s.target.startswith("<select#")}
    if not targets:
        raise ValueError("no write statements (INSERT/CREATE) to schedule")

    ids: dict[str, str] = {}
    for table in targets:
        tid = _task_id(table)
        if tid in ids.values():   # two tables collapsing to one id
            tid = f"{tid}_{len(ids)}"
        ids[table] = tid

    draft = DagDraft(dag_id=dag_id.strip(), schedule=schedule,
                     warnings=list(warnings))
    externals: set[str] = set()
    produced_lower = {t.lower(): t for t in targets}
    for table in sorted(targets):
        shape = targets[table]
        spec = TaskSpec(table=table, task_id=ids[table])
        for src in sorted(shape.sources):
            producer = produced_lower.get(src.lower())
            if producer is not None and producer != table:
                spec.upstream.append(ids[producer])
            elif producer is None:
                spec.external.append(src)
                externals.add(src)
        draft.edges += len(spec.upstream)
        draft.tasks.append(spec)
    draft.externals = sorted(externals)

    draft.python_text = _render(draft)
    ast.parse(draft.python_text)   # round-trip guard: the file must import
    return draft
