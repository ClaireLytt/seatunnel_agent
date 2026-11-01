"""Deterministic rollback orchestration for a bad data load.

Input is the incident plus the pipeline SQL (the lineage comes from the
data_lineage parser via the quality_trace helper)::

    incident = {"table": "dwd.orders",
                "partitions": ["dt=2026-10-30"],
                "restore": "snapshot",          # snapshot|rerun|overwrite
                "snapshot": "snap_dwd_orders_20261030",
                "durations": {"dws.orders_daily": 90}}   # optional, min

The plan walks DOWNSTREAM from the bad table in topological levels:
step 0 restores the table itself (a template matching the chosen
restore mode), each later level re-runs its tables — tables inside one
level carry no mutual dependency and may run in parallel — and every
touched table gets a verification SQL.  With optional per-table
durations the critical-path estimate falls out (the max of each level,
summed).  No scheduler or database connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from seatunnel_agent.agents.data.quality_trace import build_graph_from_sql

__all__ = ["RollbackPlan", "RollbackStep", "plan_rollback"]

_MODES = {"snapshot", "rerun", "overwrite"}


@dataclass
class RollbackStep:
    level: int
    table: str
    action: str            # restore / rerun / verify
    sql: str

    def to_dict(self) -> dict:
        return {"level": self.level, "table": self.table,
                "action": self.action, "sql": self.sql}


@dataclass
class RollbackPlan:
    table: str
    partitions: list[str]
    mode: str
    levels: int
    touched: list[str]
    estimated_min: float | None
    steps: list[RollbackStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"table": self.table, "partitions": self.partitions,
                "mode": self.mode, "levels": self.levels,
                "touched": self.touched,
                "estimated_min": self.estimated_min,
                "steps": [s.to_dict() for s in self.steps],
                "warnings": self.warnings}


def _part_clause(partitions: list[str]) -> str:
    if not partitions:
        return ""
    conds = " OR ".join(p.replace("=", " = '") + "'" for p in partitions)
    return f" WHERE {conds}"


def _restore_sql(table: str, partitions: list[str], mode: str,
                 snapshot: str) -> str:
    parts = ", ".join(partitions) or "<all partitions>"
    if mode == "snapshot":
        return (f"-- restore {parts} of {table} from the snapshot\n"
                f"INSERT OVERWRITE TABLE {table}"
                f"{' PARTITION (' + parts + ')' if partitions else ''}\n"
                f"SELECT * FROM {snapshot or '<snapshot_table>'}"
                f"{_part_clause(partitions)};")
    if mode == "rerun":
        return (f"-- re-run the producer job of {table} for {parts}\n"
                f"-- scheduler: clear + backfill {table} {parts}")
    return (f"-- overwrite {parts} of {table} from its own upstream\n"
            f"INSERT OVERWRITE TABLE {table}"
            f"{' PARTITION (' + parts + ')' if partitions else ''}\n"
            f"SELECT /* producer query */ ...{_part_clause(partitions)};")


def plan_rollback(sql_text: str, table: str,
                  partitions: list[str] | None = None,
                  mode: str = "rerun", snapshot: str = "",
                  durations: dict[str, float] | None = None,
                  dialect: str = "hive") -> RollbackPlan:
    mode = (mode or "rerun").strip().lower()
    if mode not in _MODES:
        raise ValueError(f"mode must be one of {sorted(_MODES)} / "
                         f"restore 方式不合法")
    partitions = [p.strip() for p in (partitions or []) if p.strip()]
    graph, warnings = build_graph_from_sql(sql_text, dialect=dialect)
    chain = graph.downstream_of(table, depth=10)
    if chain.missing_root:
        raise ValueError(f"table '{table}' not found in the SQL lineage / "
                         f"表不在血缘里")
    root = chain.root

    # topological levels downstream of the root (depth_of is positive)
    by_level: dict[int, list[str]] = {}
    for name, d in chain.depth_of.items():
        if d > 0:
            by_level.setdefault(d, []).append(name)
    levels = sorted(by_level)

    steps: list[RollbackStep] = [RollbackStep(
        level=0, table=root, action="restore",
        sql=_restore_sql(root, partitions, mode, snapshot))]
    touched = [root]
    for lv in levels:
        for name in sorted(by_level[lv]):
            touched.append(name)
            parts = ", ".join(partitions) or "<same partitions>"
            steps.append(RollbackStep(
                level=lv, table=name, action="rerun",
                sql=(f"-- level {lv}: re-run {name} for {parts} "
                     f"(parallel within the level)\n"
                     f"-- scheduler: clear + backfill {name} {parts}")))
    for name in touched:
        steps.append(RollbackStep(
            level=len(levels) + 1, table=name, action="verify",
            sql=f"SELECT COUNT(*) AS cnt FROM {name}"
                f"{_part_clause(partitions)};"))

    estimated: float | None = None
    if durations:
        estimated = float(durations.get(root, 0))
        for lv in levels:
            estimated += max(
                (float(durations.get(n, 0)) for n in by_level[lv]),
                default=0.0)
        if estimated == 0:
            estimated = None

    return RollbackPlan(table=root, partitions=partitions, mode=mode,
                        levels=len(levels), touched=touched,
                        estimated_min=estimated, steps=steps,
                        warnings=list(warnings))
