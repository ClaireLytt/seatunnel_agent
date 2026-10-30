"""Run-regression diff: this (failed) run vs a known-good baseline run.

"It worked yesterday" triage, deterministic: both runs are scanned with the
log_inspect clusterer, clusters are keyed by signature (root-cause
exception × masked message template × top frame), and the comparison
splits them into

* ``appeared``  — clusters only in the current run: the regression
  candidates, each diagnosed against the failure-signature KB so a known
  failure arrives with its cause/fix/patch attached,
* ``gone``      — clusters only in the baseline (fixed or moved),
* ``grew``      — clusters in both but with a higher count now.

The baseline's own findings are noise by definition — it succeeded — so
only the current run's new/grown clusters are diagnosed.
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
    scan_text,
)

from .diagnoser import Finding, _finding, _match, detect_engines

GROWTH_MIN_FACTOR = 2      # "grew" = at least doubled (and +1 absolute)


@dataclass
class RunDiff:
    current_root: str
    baseline_root: str
    engines: dict[str, int] = field(default_factory=dict)
    appeared: list[LogCluster] = field(default_factory=list)
    gone: list[LogCluster] = field(default_factory=list)
    grew: list[tuple[LogCluster, int]] = field(default_factory=list)
    # KB diagnosis of the appeared/grown clusters (regression candidates)
    findings: list[Finding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "appeared": len(self.appeared),
            "gone": len(self.gone),
            "grew": len(self.grew),
            "findings": len(self.findings),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_root": self.current_root,
            "baseline_root": self.baseline_root,
            "engines": dict(self.engines),
            "counts": self.counts(),
            "appeared": [c.to_dict() for c in self.appeared],
            "gone": [c.to_dict() for c in self.gone],
            "grew": [{"cluster": c.to_dict(), "baseline_count": n}
                     for c, n in self.grew],
            "findings": [f.to_dict() for f in self.findings],
            "warnings": list(self.warnings),
        }


def diff_reports(current: InspectReport, baseline: InspectReport) -> RunDiff:
    base = {c.signature: c for c in baseline.clusters}
    cur = {c.signature: c for c in current.clusters}
    diff = RunDiff(current_root=current.root, baseline_root=baseline.root,
                   warnings=list(current.warnings) + list(baseline.warnings))
    diff.engines = detect_engines(
        "\n".join(c.sample for c in current.clusters))
    for sig, c in cur.items():
        b = base.get(sig)
        if b is None:
            diff.appeared.append(c)
        elif c.count >= max(b.count * GROWTH_MIN_FACTOR, b.count + 1):
            diff.grew.append((c, b.count))
    diff.gone = [b for sig, b in base.items() if sig not in cur]
    # errors first, then by count — same ordering the clusterer uses
    def key(c: LogCluster):
        return (c.level != "error", -c.count, c.signature)
    diff.appeared.sort(key=key)
    diff.gone.sort(key=key)
    diff.grew.sort(key=lambda t: key(t[0]))
    # diagnose only the regression candidates; merge per signature
    seen: dict[str, Finding] = {}
    for cluster in diff.appeared + [c for c, _ in diff.grew]:
        sig = _match(cluster)
        if sig is None:
            continue
        f = seen.get(sig.id)
        if f is None:
            seen[sig.id] = f = _finding(sig, cluster)
            diff.findings.append(f)
        else:
            f.count += cluster.count
            for name, n in cluster.files.items():
                f.files[name] = f.files.get(name, 0) + n
    return diff


def diff_dirs(current: str | Path, baseline: str | Path,
              patterns: Iterable[str] = DEFAULT_PATTERNS) -> RunDiff:
    return diff_reports(scan_dir(current, patterns=patterns),
                        scan_dir(baseline, patterns=patterns))


def diff_texts(current: str, baseline: str) -> RunDiff:
    return diff_reports(scan_text(current, name="<current>"),
                        scan_text(baseline, name="<baseline>"))
