"""Deterministic database-runtime diagnosis from a status snapshot.

Input is a JSON snapshot pasted from monitoring or ``SHOW STATUS`` /
``SHOW PROCESSLIST`` collection scripts::

    {"variables": {"max_connections": 500},
     "status": {"threads_connected": 480, "threads_running": 95,
                "qps": 1200, "cpu_pct": 85},
     "lock_waits": [{"blocking": "trx 101", "waiting": "trx 102",
                     "table": "orders", "seconds": 42}],
     "deadlocks": 2,
     "slow_queries": [{"sql": "SELECT ...", "duration_s": 12.5,
                       "rows_examined": 8000000}]}

Every section is optional; rules fire only on the data that is present —
connection-pool pressure, running-thread storms, long lock waits,
deadlocks, slow-query hotspots and CPU saturation — each with evidence
and a prescription pointing at the sibling agent that digs deeper.
Text-in, no live database connection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

__all__ = ["DbFinding", "DbDiagnosis", "diagnose_snapshot", "parse_snapshot"]

_CONN_PCT = (80.0, 95.0)
_RUNNING = (32, 128)
_LOCK_SECONDS = (5.0, 30.0)
_SLOW_SECONDS = 1.0
_CPU_PCT = (80.0, 95.0)


@dataclass
class DbFinding:
    code: str          # DB001..
    severity: str      # high / mid / low
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail}


@dataclass
class DbDiagnosis:
    sections_seen: list[str]
    findings: list[DbFinding]

    def to_dict(self) -> dict:
        return {"sections_seen": self.sections_seen,
                "findings": [f.to_dict() for f in self.findings]}


def parse_snapshot(text: str) -> dict:
    body = (text or "").strip()
    if not body:
        raise ValueError("empty snapshot / 快照为空")
    try:
        snap = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"snapshot must be JSON: {exc}") from exc
    if not isinstance(snap, dict):
        raise ValueError("snapshot must be a JSON object / 快照须是对象")
    return snap


def _grade(value: float, thresholds: tuple[float, float]) -> str | None:
    mid, high = thresholds
    if value >= high:
        return "high"
    if value >= mid:
        return "mid"
    return None


def diagnose_snapshot(snap: dict) -> DbDiagnosis:
    findings: list[DbFinding] = []
    sections = [k for k in ("variables", "status", "lock_waits",
                            "deadlocks", "slow_queries") if k in snap]
    status = snap.get("status") or {}
    variables = snap.get("variables") or {}

    # DB001 connection-pool pressure
    max_conn = float(variables.get("max_connections") or 0)
    connected = float(status.get("threads_connected") or 0)
    if max_conn > 0 and connected > 0:
        pct = 100.0 * connected / max_conn
        sev = _grade(pct, _CONN_PCT)
        if sev:
            findings.append(DbFinding("DB001", sev, {
                "threads_connected": int(connected),
                "max_connections": int(max_conn),
                "used_pct": round(pct, 1)}))

    # DB002 running-thread storm
    running = int(status.get("threads_running") or 0)
    sev = _grade(running, _RUNNING)
    if sev:
        findings.append(DbFinding("DB002", sev, {
            "threads_running": running}))

    # DB003 long lock waits (top blockers by wait time)
    waits = [w for w in (snap.get("lock_waits") or ())
             if isinstance(w, dict)]
    long_waits = [w for w in waits
                  if float(w.get("seconds") or 0) >= _LOCK_SECONDS[0]]
    if long_waits:
        worst = max(float(w.get("seconds") or 0) for w in long_waits)
        long_waits.sort(key=lambda w: -float(w.get("seconds") or 0))
        findings.append(DbFinding(
            "DB003", _grade(worst, _LOCK_SECONDS) or "mid", {
                "count": len(long_waits), "worst_seconds": worst,
                "top": [{"blocking": w.get("blocking", "?"),
                         "waiting": w.get("waiting", "?"),
                         "table": w.get("table", "?"),
                         "seconds": float(w.get("seconds") or 0)}
                        for w in long_waits[:3]]}))

    # DB004 deadlocks
    deadlocks = snap.get("deadlocks")
    count = (len(deadlocks) if isinstance(deadlocks, list)
             else int(deadlocks or 0))
    if count > 0:
        findings.append(DbFinding("DB004", "high", {"count": count}))

    # DB005 slow-query hotspots
    slow = [q for q in (snap.get("slow_queries") or ())
            if isinstance(q, dict)
            and float(q.get("duration_s") or 0) >= _SLOW_SECONDS]
    if slow:
        slow.sort(key=lambda q: -float(q.get("duration_s") or 0))
        findings.append(DbFinding(
            "DB005", "high" if float(slow[0]["duration_s"]) >= 10 else "mid",
            {"count": len(slow),
             "top": [{"sql": str(q.get("sql", ""))[:120],
                      "duration_s": float(q.get("duration_s") or 0),
                      "rows_examined": int(q.get("rows_examined") or 0)}
                     for q in slow[:3]]}))

    # DB006 CPU saturation
    cpu = float(status.get("cpu_pct") or 0)
    sev = _grade(cpu, _CPU_PCT)
    if sev:
        findings.append(DbFinding("DB006", sev, {"cpu_pct": cpu}))

    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code))
    return DbDiagnosis(sections_seen=sections, findings=findings)
