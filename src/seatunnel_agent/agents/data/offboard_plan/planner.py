"""Deterministic table-offboarding plan from the pipeline lineage.

field_usage finds the tables nobody reads; this agent turns "let's
retire it" into a staged plan nobody gets paged for.  Paste the
pipeline SQL (quality_trace's lineage builder reused) and the table:
the plan walks DOWNSTREAM to find every consumer that must migrate
first, then stages the retirement —

1. announce — notify the consumers (listed per table, with the lineage
   distance), publish the deadline;
2. freeze — mark the table deprecated and stop the producing job
   (templates; writes stop, reads still work);
3. archive — snapshot to an archive table with a retention note;
4. drop — emitted commented-out (ddl_evolve's discipline: nothing
   destructive runs by accident).

A table with live downstream is **blocked**: the plan lists the
migrations and refuses to pretend the drop is routine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["OffboardPlan", "OffboardStep", "plan_offboard"]

_PHASES = ("announce", "freeze", "archive", "drop")


@dataclass
class OffboardStep:
    phase: str           # announce | freeze | archive | drop
    action: str          # short slug for i18n
    sql: str = ""        # template; commented when destructive
    safe: bool = True
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"phase": self.phase, "action": self.action,
                "sql": self.sql, "safe": self.safe, "detail": self.detail}


@dataclass
class OffboardPlan:
    table: str
    grace_days: int
    blocked: bool = False
    downstream: dict[str, int] = field(default_factory=dict)  # table->depth
    steps: list[OffboardStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "grace_days": self.grace_days,
                "blocked": self.blocked,
                "downstream": dict(self.downstream),
                "steps_total": len(self.steps),
                "steps": [s.to_dict() for s in self.steps],
                "warnings": list(self.warnings)}


def _commented(sql: str) -> str:
    return "\n".join("-- " + line for line in sql.splitlines())


def plan_offboard(sql_text: str, table: str, grace_days: int = 30,
                  archive_db: str = "archive",
                  dialect: str = "hive") -> OffboardPlan:
    """Pipeline SQL + table → staged offboarding plan."""
    from seatunnel_agent.agents.data.quality_trace.tracer import (
        build_graph_from_sql,
    )

    if not (table or "").strip():
        raise ValueError("'table' must not be empty")
    if grace_days < 0:
        raise ValueError("grace_days must not be negative")
    graph, warnings = build_graph_from_sql(sql_text, dialect=dialect)
    name = table.strip().lower()
    known = {t.lower(): t for t in graph.nodes}
    if name not in known:
        raise ValueError(f"table '{table}' is not in the pasted SQL's "
                         "lineage")
    real = known[name]
    chain = graph.downstream_of(real, depth=10)
    downstream = {t: d for t, d in sorted(chain.depth_of.items())
                  if d > 0} if chain else {}

    plan = OffboardPlan(table=real, grace_days=grace_days,
                        blocked=bool(downstream),
                        downstream=downstream, warnings=list(warnings))
    bare = real.split(".")[-1]
    archive = f"{archive_db}.{bare}_retired"

    if downstream:
        consumers = ", ".join(sorted(downstream))
        plan.steps.append(OffboardStep(
            phase="announce", action="migrate_consumers", safe=True,
            detail=consumers,
            sql=f"-- blocked: migrate these consumers off {real} first: "
                f"{consumers}"))
    plan.steps.append(OffboardStep(
        phase="announce", action="notify", safe=True,
        detail=f"T+{grace_days}d",
        sql=f"-- announce: {real} retires in {grace_days} day(s); "
            "post the deadline where its consumers will see it"))
    plan.steps.append(OffboardStep(
        phase="freeze", action="mark_deprecated", safe=True,
        sql=f"ALTER TABLE {real} SET TBLPROPERTIES ("
            f"'deprecated' = 'true', 'retire_after' = '<DATE+"
            f"{grace_days}d>');"))
    plan.steps.append(OffboardStep(
        phase="freeze", action="stop_producer", safe=True,
        sql=f"-- scheduler: pause the job that writes {real} "
            "(reads keep working through the grace window)"))
    plan.steps.append(OffboardStep(
        phase="archive", action="snapshot", safe=True,
        detail=archive,
        sql=f"CREATE TABLE {archive} AS SELECT * FROM {real};"))
    plan.steps.append(OffboardStep(
        phase="archive", action="verify_snapshot", safe=True,
        sql=f"SELECT COUNT(*) FROM {archive}\n"
            f"UNION ALL SELECT COUNT(*) FROM {real};  "
            "-- the two counts must match"))
    plan.steps.append(OffboardStep(
        phase="drop", action="drop_table", safe=False,
        detail=f"after T+{grace_days}d, archive verified",
        sql=_commented(f"DROP TABLE {real};")))
    return plan
