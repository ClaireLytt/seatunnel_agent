"""Deterministic CDC sync diagnosis from a replication snapshot.

Input is one sync pipeline's snapshot pasted from monitoring::

    {"source": {"binlog_file": "mysql-bin.000123", "position": 456789,
                "retention_hours": 24},
     "consumer": {"binlog_file": "mysql-bin.000120", "position": 99999,
                  "last_event_ts": "2026-10-31 10:00:00",
                  "now": "2026-10-31 12:00:00"},
     "errors": ["Duplicate entry '42' for key 'PRIMARY'",
                "ALTER TABLE orders ADD COLUMN ..."]}

Rules compare the consumer's binlog coordinates against the source
(files behind, byte lag inside one file, a consumer AHEAD of the source
— the broken-resume smell), judge event staleness from last_event_ts,
estimate the binlog-retention data-loss risk from how far behind the
consumer sits inside the retention window, and classify the pasted
errors (schema change / duplicate key / connection).  Every section is
optional.  No database connection.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

__all__ = ["CdcDiagnosis", "CdcFinding", "diagnose_cdc", "parse_cdc_snapshot"]

_FILES_BEHIND = (1, 3)
_BYTE_LAG = (10 * 1024 * 1024, 200 * 1024 * 1024)
_STALE_S = (300.0, 1800.0)
_RETENTION_SHARE = (0.5, 0.8)

_ERROR_CLASSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("schema_change", re.compile(r"(alter\s+table|schema|ddl|unknown "
                                 r"column|column count)", re.IGNORECASE)),
    ("duplicate_key", re.compile(r"(duplicate\s+(entry|key)|primary)",
                                 re.IGNORECASE)),
    ("connection", re.compile(r"(connect|timeout|eof|broken pipe|reset|"
                              r"refused)", re.IGNORECASE)),
)


@dataclass
class CdcFinding:
    code: str          # CD001..
    severity: str      # high / mid / low
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail}


@dataclass
class CdcDiagnosis:
    sections_seen: list[str]
    findings: list[CdcFinding]

    def to_dict(self) -> dict:
        return {"sections_seen": self.sections_seen,
                "findings": [f.to_dict() for f in self.findings]}


def parse_cdc_snapshot(text: str) -> dict:
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


def _file_index(name: str) -> int | None:
    m = re.search(r"(\d+)$", (name or "").strip())
    return int(m.group(1)) if m else None


def _ts(value) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _grade(value: float, thresholds: tuple[float, float]) -> str | None:
    mid, high = thresholds
    if value >= high:
        return "high"
    if value >= mid:
        return "mid"
    return None


def diagnose_cdc(snap: dict) -> CdcDiagnosis:
    findings: list[CdcFinding] = []
    sections = [k for k in ("source", "consumer", "errors") if k in snap]
    source = snap.get("source") or {}
    consumer = snap.get("consumer") or {}

    src_idx = _file_index(str(source.get("binlog_file") or ""))
    con_idx = _file_index(str(consumer.get("binlog_file") or ""))
    src_pos = int(source.get("position") or 0)
    con_pos = int(consumer.get("position") or 0)

    files_behind = 0
    if src_idx is not None and con_idx is not None:
        files_behind = src_idx - con_idx
        if files_behind < 0 or (files_behind == 0 and con_pos > src_pos
                                and src_pos > 0):
            # CD006 consumer ahead of the source: broken resume point
            findings.append(CdcFinding("CD006", "high", {
                "source": f"{source.get('binlog_file')}:{src_pos}",
                "consumer": f"{consumer.get('binlog_file')}:{con_pos}"}))
        elif files_behind > 0:
            sev = _grade(files_behind, _FILES_BEHIND)
            findings.append(CdcFinding("CD001", sev or "mid", {
                "files_behind": files_behind,
                "source_file": source.get("binlog_file"),
                "consumer_file": consumer.get("binlog_file")}))
        elif src_pos > 0 and con_pos >= 0:
            byte_lag = src_pos - con_pos
            sev = _grade(byte_lag, _BYTE_LAG)
            if sev:
                findings.append(CdcFinding("CD002", sev, {
                    "byte_lag": byte_lag,
                    "file": source.get("binlog_file")}))

    # CD003 event staleness
    last = _ts(consumer.get("last_event_ts"))
    now = _ts(consumer.get("now")) or _ts(snap.get("now"))
    if last is not None and now is not None:
        stale_s = max(0.0, (now - last).total_seconds())
        sev = _grade(stale_s, _STALE_S)
        if sev:
            findings.append(CdcFinding("CD003", sev, {
                "stale_s": round(stale_s),
                "last_event_ts": str(consumer.get("last_event_ts"))}))
        # CD004 retention risk: the lag eats into the binlog window
        retention_h = float(source.get("retention_hours") or 0)
        if retention_h > 0 and files_behind >= 0:
            share = (stale_s / 3600.0) / retention_h
            sev = _grade(share, _RETENTION_SHARE)
            if sev:
                findings.append(CdcFinding("CD004", "high", {
                    "behind_h": round(stale_s / 3600.0, 1),
                    "retention_h": retention_h,
                    "share_pct": round(100 * share, 1)}))

    # CD005 error classification
    errors = [str(e) for e in (snap.get("errors") or ()) if str(e).strip()]
    if errors:
        classes: dict[str, list[str]] = {}
        for e in errors:
            kind = "other"
            for name, pat in _ERROR_CLASSES:
                if pat.search(e):
                    kind = name
                    break
            classes.setdefault(kind, []).append(e[:100])
        findings.append(CdcFinding(
            "CD005", "high" if "schema_change" in classes else "mid",
            {"count": len(errors),
             "classes": {k: v[:2] for k, v in classes.items()}}))

    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code))
    return CdcDiagnosis(sections_seen=sections, findings=findings)
