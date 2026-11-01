"""Deterministic Flink job health diagnosis from a snapshot.

Input is one job's snapshot pasted from the REST API or the UI::

    {"job": "sync-orders",
     "checkpoints": [{"id": 101, "duration_ms": 8000,
                      "size_bytes": 1073741824, "failed": false,
                      "alignment_ms": 500}],
     "operators": [{"name": "join-enrich", "backpressure": 0.85,
                    "busy": 0.4, "watermark_lag_ms": 420000}],
     "restarts": {"count_1h": 2, "last_cause": "TaskManager lost"}}

Every section is optional; rules fire only on what is present —
checkpoint failures, duration blow-ups (vs the median of the earlier
checkpoints), alignment-dominated checkpoints (the unaligned-checkpoint
smell), backpressured operators, watermark lag and restart churn — each
with evidence and a prescription pointing at the sibling agent that digs
deeper (kafkalag for source backlog, skew-runtime for task skew).  No
cluster connection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

__all__ = ["FlinkDiagnosis", "FlinkFinding", "diagnose_job",
           "parse_job_snapshot"]

_CKPT_MS = (60_000.0, 300_000.0)
_CKPT_BLOWUP = 2.0          # latest vs median of the earlier ones
_ALIGN_SHARE = 0.5
_BACKPRESSURE = (0.5, 0.8)
_WATERMARK_MS = (60_000.0, 300_000.0)
_RESTARTS = (1, 3)


@dataclass
class FlinkFinding:
    code: str          # FD001..
    severity: str      # high / mid / low
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail}


@dataclass
class FlinkDiagnosis:
    job: str
    sections_seen: list[str]
    findings: list[FlinkFinding]

    def to_dict(self) -> dict:
        return {"job": self.job, "sections_seen": self.sections_seen,
                "findings": [f.to_dict() for f in self.findings]}


def parse_job_snapshot(text: str) -> dict:
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


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _grade(value: float, thresholds: tuple[float, float]) -> str | None:
    mid, high = thresholds
    if value >= high:
        return "high"
    if value >= mid:
        return "mid"
    return None


def diagnose_job(snap: dict) -> FlinkDiagnosis:
    findings: list[FlinkFinding] = []
    sections = [k for k in ("checkpoints", "operators", "restarts")
                if k in snap]
    ckpts = [c for c in (snap.get("checkpoints") or ())
             if isinstance(c, dict)]
    ops = [o for o in (snap.get("operators") or ()) if isinstance(o, dict)]

    # FD001 checkpoint failures
    failed = [c for c in ckpts if c.get("failed")]
    if failed:
        latest_failed = bool(ckpts and ckpts[-1].get("failed"))
        findings.append(FlinkFinding(
            "FD001",
            "high" if len(failed) >= 3 or latest_failed else "mid",
            {"failed": len(failed), "total": len(ckpts),
             "latest_failed": latest_failed}))

    # FD002 checkpoint duration blow-up or absolute ceiling
    oks = [c for c in ckpts if not c.get("failed")]
    if oks:
        last = float(oks[-1].get("duration_ms") or 0)
        earlier = [float(c.get("duration_ms") or 0) for c in oks[:-1]]
        med = _median(earlier) if earlier else 0.0
        sev = _grade(last, _CKPT_MS)
        blowup = med > 0 and last >= _CKPT_BLOWUP * med
        if sev or blowup:
            findings.append(FlinkFinding(
                "FD002", sev or "mid",
                {"last_ms": last, "median_ms": round(med),
                 "ratio": round(last / med, 1) if med > 0 else None}))
        # FD003 alignment dominated
        align = float(oks[-1].get("alignment_ms") or 0)
        if last > 0 and align / last >= _ALIGN_SHARE:
            findings.append(FlinkFinding("FD003", "mid", {
                "alignment_ms": align, "duration_ms": last,
                "share_pct": round(100 * align / last, 1)}))

    # FD004 backpressured operators (worst one carries the finding)
    pressured = [o for o in ops
                 if _grade(float(o.get("backpressure") or 0),
                           _BACKPRESSURE)]
    if pressured:
        worst = max(pressured, key=lambda o: float(o["backpressure"]))
        ratio = float(worst["backpressure"])
        findings.append(FlinkFinding(
            "FD004", _grade(ratio, _BACKPRESSURE) or "mid",
            {"operator": str(worst.get("name") or "?"),
             "backpressure": ratio, "count": len(pressured)}))

    # FD005 watermark lag
    laggy = [(str(o.get("name") or "?"), float(o.get("watermark_lag_ms")
                                               or 0))
             for o in ops if _grade(float(o.get("watermark_lag_ms") or 0),
                                    _WATERMARK_MS)]
    if laggy:
        laggy.sort(key=lambda x: -x[1])
        name, lag = laggy[0]
        findings.append(FlinkFinding(
            "FD005", _grade(lag, _WATERMARK_MS) or "mid",
            {"operator": name, "watermark_lag_ms": lag,
             "count": len(laggy)}))

    # FD006 restart churn
    restarts = snap.get("restarts")
    count = (int(restarts.get("count_1h") or 0)
             if isinstance(restarts, dict) else int(restarts or 0))
    if count >= _RESTARTS[0]:
        cause = (str(restarts.get("last_cause") or "")
                 if isinstance(restarts, dict) else "")
        findings.append(FlinkFinding(
            "FD006", "high" if count >= _RESTARTS[1] else "mid",
            {"count_1h": count, "last_cause": cause}))

    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code))
    return FlinkDiagnosis(job=str(snap.get("job") or ""),
                          sections_seen=sections, findings=findings)
