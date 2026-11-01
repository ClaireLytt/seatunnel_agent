"""Deterministic partition-key selection for an unpartitioned table.

partition_health examines the partitions a table already has; this
agent picks the key for a table that has none yet.  Paste a data sample
(sample_profile's parser and profiles reused) plus the query workload
that will hit the table (sqlglot), and every column is scored as a
partition-key candidate:

* **filter share** — how many queries' WHERE clauses touch it (a
  partition key nobody filters on prunes nothing);
* **time shape** — date/datetime columns (or dt/date/ts names) get the
  canonical-key bonus;
* **cardinality band** — the sample's distinct count must land in the
  sweet band (2..5000): one value partitions nothing, an id-like column
  explodes the metastore.

High-cardinality columns that are hot in filters or joins get a
``CLUSTERED BY`` bucketing suggestion instead.  Findings: PP001 no
time-shaped column (medium), PP002 the hottest filter column is
unsuitable as a partition key (medium, bucket it), PP003 queries whose
WHERE touches no sampled column — unprunable full scans (low).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["PartitionPlan", "PlanFinding", "plan_partitions"]

_TIME_NAME = re.compile(r"(^|_)(dt|date|day|ts|time|month|hour)(_|$)",
                        re.IGNORECASE)
_ID_NAME = re.compile(r"(^id$|_id$)", re.IGNORECASE)
_SWEET_LO, _SWEET_HI = 2, 5000


def _buckets_for(distinct: int) -> int:
    if distinct <= 10_000:
        return 8
    if distinct <= 100_000:
        return 32
    return 64


@dataclass
class Candidate:
    column: str
    kind: str
    distinct: int
    filter_hits: int = 0
    score: float = 0.0
    verdict: str = ""        # recommend | possible | unsuitable
    reason: str = ""         # i18n key suffix

    def to_dict(self) -> dict[str, Any]:
        return {"column": self.column, "kind": self.kind,
                "distinct": self.distinct,
                "filter_hits": self.filter_hits,
                "score": round(self.score, 2),
                "verdict": self.verdict, "reason": self.reason}


@dataclass
class PlanFinding:
    code: str            # PP001..PP003
    severity: str        # medium | low
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail}


@dataclass
class PartitionPlan:
    queries_total: int = 0
    candidates: list[Candidate] = field(default_factory=list)
    partition_by: str = ""           # recommended clause, may be ""
    cluster_by: str = ""             # optional bucketing clause
    findings: list[PlanFinding] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"queries_total": self.queries_total,
                "partition_by": self.partition_by,
                "cluster_by": self.cluster_by,
                "counts": self.counts(),
                "candidates": [c.to_dict() for c in self.candidates],
                "findings": [f.to_dict() for f in self.findings]}


def _where_columns(queries_text: str, dialect: str) -> tuple[list[set[str]],
                                                             int]:
    """Per-query set of lower-cased column names referenced in WHERE."""
    import sqlglot
    from sqlglot import exp

    from seatunnel_agent.agents.data.data_lineage.sqlglot_lineage import (
        resolve_sqlglot_dialect,
    )

    try:
        trees = sqlglot.parse(queries_text,
                              read=resolve_sqlglot_dialect(dialect))
    except sqlglot.errors.ParseError as exc:
        raise ValueError(f"queries: cannot parse ({str(exc)[:200]})")
    per_query: list[set[str]] = []
    total = 0
    for tree in trees:
        if tree is None:
            continue
        total += 1
        cols: set[str] = set()
        for where in tree.find_all(exp.Where):
            for col in where.find_all(exp.Column):
                if col.name:
                    cols.add(col.name.lower())
        per_query.append(cols)
    if not total:
        raise ValueError("the query workload has no statements")
    return per_query, total


def plan_partitions(headers: list[str], rows: list[dict[str, str | None]],
                    queries_text: str,
                    dialect: str = "hive") -> PartitionPlan:
    """Sample + workload → ranked partition-key candidates."""
    from seatunnel_agent.agents.data.sample_profile import profile_rows

    if not headers or not rows:
        raise ValueError("the sample needs a header and at least one row")
    per_query, total = _where_columns(queries_text, dialect)
    profiles = {p.name: p for p in profile_rows(headers, rows).columns}

    plan = PartitionPlan(queries_total=total)
    header_set = {h.lower() for h in headers}
    unprunable = sum(1 for cols in per_query if not (cols & header_set))

    for h in headers:
        p = profiles[h]
        values = {str(r[h]) for r in rows if r.get(h) not in (None, "")}
        c = Candidate(column=h, kind=p.kind, distinct=len(values))
        c.filter_hits = sum(1 for cols in per_query if h.lower() in cols)
        timey = (p.kind in ("date", "datetime", "date_slash")
                 or bool(_TIME_NAME.search(h)))
        sweet = _SWEET_LO <= c.distinct <= _SWEET_HI
        c.score = (c.filter_hits / total * 3
                   + (2.0 if timey else 0.0)
                   + (1.0 if sweet else -1.0))
        if c.distinct < _SWEET_LO:
            c.verdict, c.reason = "unsuitable", "single_value"
        elif c.distinct > _SWEET_HI:
            c.verdict, c.reason = "unsuitable", "too_many"
        elif timey and c.filter_hits:
            c.verdict, c.reason = "recommend", "time_filtered"
        elif timey:
            c.verdict, c.reason = "recommend", "time_shaped"
        elif c.filter_hits:
            c.verdict, c.reason = "possible", "filtered"
        else:
            c.verdict, c.reason = "possible", "unfiltered"
        plan.candidates.append(c)
    plan.candidates.sort(key=lambda c: (-c.score, c.column))

    best = next((c for c in plan.candidates if c.verdict == "recommend"),
                None)
    if best is not None:
        plan.partition_by = f"PARTITIONED BY ({best.column})"
    hot = max(plan.candidates, key=lambda c: (c.filter_hits, c.distinct))
    if (hot.filter_hits and hot.distinct > _SWEET_HI
            and _ID_NAME.search(hot.column)):
        plan.cluster_by = (f"CLUSTERED BY ({hot.column}) INTO "
                           f"{_buckets_for(hot.distinct)} BUCKETS")

    if not any(c.verdict == "recommend" for c in plan.candidates):
        plan.findings.append(PlanFinding("PP001", "medium"))
    if (hot.filter_hits and hot.verdict == "unsuitable"):
        plan.findings.append(PlanFinding(
            "PP002", "medium",
            f"{hot.column} ({hot.distinct} distinct)"))
    if unprunable:
        plan.findings.append(PlanFinding("PP003", "low", str(unprunable)))
    return plan
