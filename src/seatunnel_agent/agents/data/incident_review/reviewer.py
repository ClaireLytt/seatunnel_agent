"""Deterministic incident timeline review from an event log.

After the fire is out, somebody has to write the postmortem — and the
numbers in it (how late we noticed, how long until hands on keyboard,
how long to recovery) are usually guessed.  Paste the incident's event
log — columns ``time`` (ISO datetime, or ``HH:MM`` all in one day),
``kind`` (``impact`` | ``alert`` | ``action`` | ``comm`` |
``recovery``), ``text`` — and the review computes them:

* **MTTD** — first impact → first alert (how late the monitoring was);
* **MTTA** — first alert → first action (how long until response);
* **MTTR** — first impact → last recovery (the outage the consumers
  felt);

graded: IR001 detection lag over 15 min, IR002 response lag over
15 min, IR003 silent windows over 30 min inside the incident (nobody
logged anything), IR004 no recovery event at all (the postmortem has no
end), each medium, high at 4x the bound.  Times must use one format per
paste (the sla_board lesson: mixed scales score garbage silently).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["IncidentFinding", "IncidentReview", "review_incident"]

_KINDS = ("impact", "alert", "action", "comm", "recovery")
_HM_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_DETECT_MIN = 15.0
_RESPOND_MIN = 15.0
_SILENT_MIN = 30.0
_HIGH_FACTOR = 4.0


@dataclass
class Event:
    minute: float        # minutes since the first event
    kind: str
    text: str
    raw_time: str

    def to_dict(self) -> dict[str, Any]:
        return {"minute": round(self.minute, 1), "kind": self.kind,
                "text": self.text, "time": self.raw_time}


@dataclass
class IncidentFinding:
    code: str            # IR001..IR004
    severity: str        # high | medium
    value: float = 0.0
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "value": round(self.value, 1), "detail": self.detail}


@dataclass
class IncidentReview:
    events: list[Event] = field(default_factory=list)
    mttd_min: float | None = None
    mtta_min: float | None = None
    mttr_min: float | None = None
    findings: list[IncidentFinding] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"events_total": len(self.events),
                "mttd_min": self.mttd_min, "mtta_min": self.mtta_min,
                "mttr_min": self.mttr_min,
                "counts": self.counts(),
                "events": [e.to_dict() for e in self.events],
                "findings": [f.to_dict() for f in self.findings]}


def _to_minutes(value: str, what: str) -> tuple[float, str]:
    v = (value or "").strip()
    m = _HM_RE.match(v)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2)), "hm"
    try:
        from datetime import datetime

        return datetime.fromisoformat(v).timestamp() / 60, "iso"
    except ValueError:
        raise ValueError(f"{what}: cannot parse time '{v}' "
                         "(use HH:MM or an ISO datetime)")


def _grade(value: float, bound: float) -> str:
    return "high" if value >= bound * _HIGH_FACTOR else "medium"


def review_incident(headers: list[str],
                    rows: list[dict[str, str | None]]) -> IncidentReview:
    """Incident event log → timeline metrics, graded."""
    needed = {"time", "kind", "text"}
    missing = needed - {h.lower() for h in headers}
    if missing:
        raise ValueError("the log needs columns time/kind/text — "
                         f"missing: {', '.join(sorted(missing))}")
    if not rows:
        raise ValueError("the event log has no rows")
    col = {h.lower(): h for h in headers}

    parsed: list[tuple[float, str, str, str]] = []
    fmt_seen: str | None = None
    for i, r in enumerate(rows):
        kind = str(r.get(col["kind"]) or "").strip().lower()
        if kind not in _KINDS:
            raise ValueError(f"row {i + 1}: kind must be one of "
                             f"{', '.join(_KINDS)} (got '{kind}')")
        raw = str(r.get(col["time"]) or "")
        minute, fmt = _to_minutes(raw, f"row {i + 1}")
        if fmt_seen is None:
            fmt_seen = fmt
        elif fmt != fmt_seen:
            raise ValueError(f"row {i + 1}: the log mixes HH:MM with ISO "
                             "datetimes — use one format per paste")
        parsed.append((minute, kind, str(r.get(col["text"]) or "").strip(),
                       raw.strip()))
    parsed.sort(key=lambda t: t[0])
    t0 = parsed[0][0]

    review = IncidentReview(events=[
        Event(minute=m - t0, kind=k, text=txt, raw_time=raw)
        for m, k, txt, raw in parsed])

    def first(kind: str) -> float | None:
        return next((e.minute for e in review.events if e.kind == kind),
                    None)

    impact = first("impact")
    alert = first("alert")
    action = first("action")
    recovery_events = [e.minute for e in review.events
                       if e.kind == "recovery"]
    if impact is None:
        raise ValueError("the log has no 'impact' event — mark when the "
                         "incident started")

    if alert is not None and alert >= impact:
        review.mttd_min = round(alert - impact, 1)
    if alert is not None and action is not None and action >= alert:
        review.mtta_min = round(action - alert, 1)
    if recovery_events:
        review.mttr_min = round(max(recovery_events) - impact, 1)

    if review.mttd_min is not None and review.mttd_min >= _DETECT_MIN:
        review.findings.append(IncidentFinding(
            "IR001", _grade(review.mttd_min, _DETECT_MIN),
            review.mttd_min))
    if review.mtta_min is not None and review.mtta_min >= _RESPOND_MIN:
        review.findings.append(IncidentFinding(
            "IR002", _grade(review.mtta_min, _RESPOND_MIN),
            review.mtta_min))
    end = (max(recovery_events) if recovery_events
           else review.events[-1].minute)
    prev = impact
    worst_gap, gap_at = 0.0, 0.0
    for e in review.events:
        if e.minute < impact or e.minute > end:
            continue
        if e.minute - prev > worst_gap:
            worst_gap, gap_at = e.minute - prev, prev
        prev = e.minute
    if worst_gap >= _SILENT_MIN:
        review.findings.append(IncidentFinding(
            "IR003", _grade(worst_gap, _SILENT_MIN), worst_gap,
            f"@{gap_at:g}min"))
    if not recovery_events:
        review.findings.append(IncidentFinding("IR004", "high"))

    order = {"high": 0, "medium": 1}
    review.findings.sort(key=lambda f: (order[f.severity], f.code))
    return review
