"""Deterministic pipeline failure diagnosis.

Reuses log_inspect's exception extraction/clustering, then layers engine
detection and knowledge-base signature matching on top: each error cluster
either maps to a known failure signature (with cause + fix) or lands in the
unmatched list. The highest-severity, earliest finding is the primary
suspect — later failures are usually fallout from the first one.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from seatunnel_agent.agents.data.log_inspect.clusterer import (
    DEFAULT_PATTERNS,
    InspectReport,
    LogCluster,
    scan_dir,
    scan_files,
    scan_text,
)

from .kb import ENGINE_MARKERS, SEVERITY_RANK, SIGNATURES, Signature

MAX_UNMATCHED = 10


@dataclass
class Finding:
    """One KB signature hit on one cluster."""

    sig_id: str
    engine: str
    severity: str        # critical | error | warn
    title_zh: str
    title_en: str
    cause_zh: str
    cause_en: str
    fix_zh: str
    fix_en: str
    patch: str          # copy-paste fix patch; "" when none applies
    exception: str
    template: str
    count: int
    files: dict[str, int]
    first_ts: str
    last_ts: str
    sample: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sig_id": self.sig_id,
            "engine": self.engine,
            "severity": self.severity,
            "title_zh": self.title_zh, "title_en": self.title_en,
            "cause_zh": self.cause_zh, "cause_en": self.cause_en,
            "fix_zh": self.fix_zh, "fix_en": self.fix_en,
            "patch": self.patch,
            "exception": self.exception,
            "template": self.template,
            "count": self.count,
            "files": dict(self.files),
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
            "sample": self.sample,
        }


@dataclass
class Diagnosis:
    root: str
    engines: dict[str, int] = field(default_factory=dict)  # marker hit counts
    findings: list[Finding] = field(default_factory=list)
    unmatched: list[LogCluster] = field(default_factory=list)
    files_scanned: int = 0
    lines_scanned: int = 0
    events: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def primary(self) -> Finding | None:
        return self.findings[0] if self.findings else None

    def counts(self) -> dict[str, int]:
        out = {"critical": 0, "error": 0, "warn": 0}
        for f in self.findings:
            out[f.severity] = out.get(f.severity, 0) + 1
        out["findings"] = len(self.findings)
        out["unmatched"] = len(self.unmatched)
        return out


def detect_engines(text: str) -> dict[str, int]:
    """Marker hit counts per engine over the scanned samples."""
    hits: dict[str, int] = {}
    for engine, marker in ENGINE_MARKERS:
        n = len(marker.findall(text))
        if n:
            hits[engine] = n
    return hits


def _match(cluster: LogCluster) -> Signature | None:
    """First KB signature matching the cluster's exception+message+sample."""
    haystack = f"{cluster.exception}: {cluster.template}\n{cluster.sample}"
    for sig in SIGNATURES:
        if sig.pattern.search(haystack):
            return sig
    return None


def _finding(sig: Signature, c: LogCluster) -> Finding:
    return Finding(
        sig_id=sig.id, engine=sig.engine, severity=sig.severity,
        title_zh=sig.title_zh, title_en=sig.title_en,
        cause_zh=sig.cause_zh, cause_en=sig.cause_en,
        fix_zh=sig.fix_zh, fix_en=sig.fix_en, patch=sig.patch,
        exception=c.exception, template=c.template, count=c.count,
        files=dict(c.files), first_ts=c.first_ts, last_ts=c.last_ts,
        sample=c.sample)


def diagnose_report(report: InspectReport) -> Diagnosis:
    """Diagnosis from an already-scanned InspectReport."""
    diag = Diagnosis(root=report.root,
                     files_scanned=report.files_scanned,
                     lines_scanned=report.lines_scanned,
                     events=report.events,
                     warnings=list(report.warnings))
    sample_text = "\n".join(c.sample for c in report.clusters)
    diag.engines = detect_engines(sample_text)
    seen: set[str] = set()   # one finding per signature; clusters merge into it
    by_id: dict[str, Finding] = {}
    for cluster in report.clusters:
        sig = _match(cluster)
        if sig is None:
            if cluster.level == "error" and len(diag.unmatched) < MAX_UNMATCHED:
                diag.unmatched.append(cluster)
            continue
        if sig.id in seen:
            f = by_id[sig.id]
            f.count += cluster.count
            for name, n in cluster.files.items():
                f.files[name] = f.files.get(name, 0) + n
            continue
        seen.add(sig.id)
        by_id[sig.id] = _finding(sig, cluster)
        diag.findings.append(by_id[sig.id])
    # primary suspect first: severity, then earliest occurrence, then count
    diag.findings.sort(key=lambda f: (
        -SEVERITY_RANK.get(f.severity, 0),
        f.first_ts or "9999",
        -f.count))
    return diag


def diagnose_text(text: str, name: str = "<inline>") -> Diagnosis:
    return diagnose_report(scan_text(text, name=name, include_warn=True))


def diagnose_dir(directory: str | Path,
                 patterns: Iterable[str] = DEFAULT_PATTERNS) -> Diagnosis:
    return diagnose_report(scan_dir(directory, patterns=patterns,
                                    include_warn=True))


def diagnose_files(paths: Iterable[Path] | Iterable[str],
                   root: str = "") -> Diagnosis:
    return diagnose_report(scan_files(paths, include_warn=True, root=root))
