"""Deterministic scheduler-file drafts (Airflow / DolphinScheduler /
Azkaban) from pipeline SQL.

dag_check diagnoses a dependency graph; this agent ships the scheduler
file.  Paste the pipeline SQL (sql_diff's statement shapes reused):
every write target becomes a task, the dependency edges come from which
targets read which, external source tables surface as wait-sensor
placeholders, and the output is a runnable Airflow DAG skeleton —
one BashOperator per task with a ``<RUN {table}>`` placeholder command,
``task_id`` sanitized from the table name, edges wired with ``>>``.
``engine`` picks the output: Airflow dag.py (default), a
DolphinScheduler process-definition JSON (SHELL tasks + relations), or
an Azkaban Flow 2.0 YAML (command nodes + dependsOn).  Every draft is
round-tripped (``ast.parse`` / ``json.loads`` / ``yaml.safe_load``)
before it is returned, so the file always loads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = ["DagDraft", "TaskSpec", "generate_dag"]

_IDENT = re.compile(r"[^0-9A-Za-z_]+")
_ENGINES = ("airflow", "dolphinscheduler", "azkaban")


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
    engine: str = "airflow"
    tasks: list[TaskSpec] = field(default_factory=list)
    externals: list[str] = field(default_factory=list)  # all external tables
    edges: int = 0
    python_text: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"dag_id": self.dag_id, "schedule": self.schedule,
                "engine": self.engine,
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


def _render_dolphinscheduler(draft: DagDraft) -> str:
    """DolphinScheduler process definition (SHELL tasks + relations)."""
    import json

    codes = {t.task_id: i + 1 for i, t in enumerate(draft.tasks)}
    task_defs = []
    relations = []
    for t in draft.tasks:
        desc = ""
        if t.external:
            desc = ("upstream outside this script: "
                    + ", ".join(t.external))
        task_defs.append({
            "code": codes[t.task_id], "name": t.task_id,
            "taskType": "SHELL", "description": desc,
            "taskParams": {"rawScript": f"echo <RUN {t.table}>",
                           "localParams": [], "resourceList": []},
            "flag": "YES", "taskPriority": "MEDIUM",
            "failRetryTimes": 0, "failRetryInterval": 1,
            "timeoutFlag": "CLOSE"})
        if t.upstream:
            for up in t.upstream:
                relations.append({"name": "",
                                  "preTaskCode": codes[up],
                                  "postTaskCode": codes[t.task_id]})
        else:
            relations.append({"name": "", "preTaskCode": 0,
                              "postTaskCode": codes[t.task_id]})
    doc = {"name": draft.dag_id,
           "description": "auto-drafted - replace every <RUN ...> "
                          "placeholder before deploying",
           "schedule": {"crontab": draft.schedule},
           "taskDefinitionList": task_defs,
           "taskRelationList": relations}
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def _render_azkaban(draft: DagDraft) -> str:
    """Azkaban Flow 2.0 YAML (command nodes + dependsOn)."""
    import json

    lines = ["# Auto-drafted Azkaban flow - replace every <RUN ...>",
             "# placeholder before deploying.",
             "config:",
             f"  schedule: {json.dumps(draft.schedule)}",
             "nodes:"]
    for t in draft.tasks:
        if t.external:
            ext = ", ".join(t.external)
            lines.append(f"  # upstream outside this script: {ext}")
        lines += [f"  - name: {t.task_id}",
                  "    type: command",
                  "    config:",
                  "      command: "
                  + json.dumps(f"echo <RUN {t.table}>")]
        if t.upstream:
            lines.append("    dependsOn:")
            lines += [f"      - {up}" for up in t.upstream]
    return "\n".join(lines) + "\n"


def generate_dag(sql_text: str, dag_id: str = "pipeline",
                 schedule: str = "0 2 * * *",
                 dialect: str = "hive",
                 engine: str = "airflow") -> DagDraft:
    """Pipeline SQL → importable scheduler file (per *engine*)."""
    import ast

    from seatunnel_agent.agents.data.sql_diff.differ import statement_shapes

    if engine not in _ENGINES:
        raise ValueError(f"engine must be one of {_ENGINES}")
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
                     engine=engine, warnings=list(warnings))
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

    # round-trip guard: whatever the engine, the file must load clean
    if engine == "dolphinscheduler":
        import json

        draft.python_text = _render_dolphinscheduler(draft)
        doc = json.loads(draft.python_text)
        if len(doc["taskDefinitionList"]) != len(draft.tasks):
            raise ValueError("internal: the generated definition lost "
                             "tasks in the round-trip")
    elif engine == "azkaban":
        import yaml

        draft.python_text = _render_azkaban(draft)
        doc = yaml.safe_load(draft.python_text)
        if len(doc["nodes"]) != len(draft.tasks):
            raise ValueError("internal: the generated flow lost tasks "
                             "in the round-trip")
    else:
        draft.python_text = _render(draft)
        ast.parse(draft.python_text)   # the dag.py must import
    return draft
