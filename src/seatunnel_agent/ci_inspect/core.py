# -*- coding: utf-8 -*-
"""CI log triage core — cluster failures, spot flaky jobs, duration drift.

Deterministic and offline.  Two independent inputs:

* **job logs** (GitHub-Actions style text, timestamp prefixes tolerated) —
  error events are extracted (``##[error]``, tracebacks, ``FAILED``/
  ``Error:`` lines), normalized into templates (numbers/paths/hashes
  masked) and clustered, collapsing noisy logs into Top-N root causes;
* **runs metadata** (JSON list) — flaky detection (same workflow + same
  commit with both success and failure) and duration drift (latest run vs
  the median of its history).

Fetching live data is a CLI convenience (``gh api`` subprocess); the core
never touches the network.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import median
from typing import Any

_TS_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+Z\s?")
_ERROR_MARKERS = re.compile(
    r"##\[error\]|^Traceback \(most recent call last\)|"
    r"^(?:FAILED|ERROR)\b|[A-Za-z]*Error\b|\berror\[|npm ERR!|FATAL", re.M)

# template normalization: volatile tokens → placeholders
_NORMALIZERS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b[0-9a-f]{7,40}\b"), "<hash>"),
    (re.compile(r"\b\d+(\.\d+)+\b"), "<ver>"),
    (re.compile(r"\b\d+\b"), "<n>"),
    (re.compile(r"(?:[A-Za-z]:)?[\\/][\w.\\/-]{6,}"), "<path>"),
    (re.compile(r"'[^']{1,80}'"), "'<s>'"),
    (re.compile(r"\"[^\"]{1,80}\""), '"<s>"'),
    (re.compile(r"\s+"), " "),
]

DURATION_DRIFT_FACTOR = 1.5
_MIN_HISTORY = 3


@dataclass
class Cluster:
    template: str
    count: int = 0
    jobs: set = field(default_factory=set)
    sample: str = ""           # first raw line (timestamp stripped)

    def to_dict(self) -> dict[str, Any]:
        return {"template": self.template, "count": self.count,
                "jobs": sorted(self.jobs), "sample": self.sample}


@dataclass
class RunsInsight:
    flaky: list[dict[str, Any]] = field(default_factory=list)
    drift: list[dict[str, Any]] = field(default_factory=list)
    workflows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CiReport:
    clusters: list[Cluster] = field(default_factory=list)
    runs: RunsInsight = field(default_factory=RunsInsight)
    error_events: int = 0
    logs_analyzed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"clusters": [c.to_dict() for c in self.clusters],
                "error_events": self.error_events,
                "logs_analyzed": self.logs_analyzed,
                "flaky": self.runs.flaky, "drift": self.runs.drift,
                "workflows": self.runs.workflows}


def normalize_template(line: str) -> str:
    out = _TS_PREFIX.sub("", line)
    out = out.replace("##[error]", "").strip()
    for pat, repl in _NORMALIZERS:
        out = pat.sub(repl, out)
    return out.strip()[:200]


def extract_error_lines(text: str) -> list[str]:
    """Error-ish lines with the timestamp prefix stripped."""
    out = []
    for line in (text or "").splitlines():
        stripped = _TS_PREFIX.sub("", line)
        if _ERROR_MARKERS.search(stripped):
            out.append(stripped.strip())
    return out


def cluster_logs(logs: dict[str, str], top: int = 10) -> tuple[list[Cluster], int]:
    """{job name: log text} → Top-N clusters + total error-event count."""
    clusters: dict[str, Cluster] = {}
    events = 0
    for job, text in logs.items():
        for raw in extract_error_lines(text):
            events += 1
            key = normalize_template(raw)
            if not key:
                continue
            c = clusters.setdefault(key, Cluster(template=key, sample=raw))
            c.count += 1
            c.jobs.add(job)
    ordered = sorted(clusters.values(),
                     key=lambda c: (-c.count, c.template))[:top]
    return ordered, events


# ── runs metadata ───────────────────────────────────────────────────────────

def parse_runs(text: str) -> list[dict[str, Any]]:
    """JSON list of runs: {workflow, conclusion, head_sha, duration_s,
    [run_number]}.  ``gh api``'s shape is converted by the CLI helper."""
    try:
        raw = json.loads(text or "[]")
    except ValueError as exc:
        raise ValueError(f"runs JSON 解析失败: {exc}")
    if isinstance(raw, dict):
        raw = raw.get("runs") or raw.get("workflow_runs") or []
    if not isinstance(raw, list):
        raise ValueError("runs JSON 期望为列表")
    runs = []
    for i, r in enumerate(raw):
        if not isinstance(r, dict):
            raise ValueError(f"runs[{i}] 必须是对象")
        runs.append({
            "workflow": str(r.get("workflow") or r.get("name") or "?"),
            "conclusion": str(r.get("conclusion") or ""),
            "head_sha": str(r.get("head_sha") or "")[:12],
            "duration_s": float(r.get("duration_s") or 0),
            "run_number": r.get("run_number"),
        })
    return runs


def analyze_runs(runs: list[dict[str, Any]]) -> RunsInsight:
    insight = RunsInsight()
    by_wf: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        by_wf[r["workflow"]].append(r)

    for wf in sorted(by_wf):
        rows = by_wf[wf]
        done = [r for r in rows if r["conclusion"] in ("success", "failure")]
        fails = sum(1 for r in done if r["conclusion"] == "failure")
        insight.workflows.append({
            "workflow": wf, "runs": len(rows), "failures": fails,
            "fail_rate": round(fails / len(done), 3) if done else 0.0,
        })
        # flaky: both success and failure on the SAME commit
        by_sha: dict[str, set] = defaultdict(set)
        for r in done:
            if r["head_sha"]:
                by_sha[r["head_sha"]].add(r["conclusion"])
        for sha in sorted(s for s, c in by_sha.items()
                          if {"success", "failure"} <= c):
            insight.flaky.append({"workflow": wf, "head_sha": sha})
        # duration drift: latest vs median of its predecessors.
        # gh api returns runs NEWEST-first — order by run_number when the
        # data carries it, else trust the input order (demo files are
        # oldest-first).
        timed = [r for r in rows if r["duration_s"] > 0]
        if timed and all(r.get("run_number") is not None for r in timed):
            timed.sort(key=lambda r: r["run_number"])
        if len(timed) >= _MIN_HISTORY + 1:
            latest, history = timed[-1], timed[:-1]
            base = median(r["duration_s"] for r in history)
            if base > 0 and latest["duration_s"] > DURATION_DRIFT_FACTOR * base:
                insight.drift.append({
                    "workflow": wf,
                    "latest_s": round(latest["duration_s"], 1),
                    "median_s": round(base, 1),
                    "factor": round(latest["duration_s"] / base, 2),
                })
    return insight


def analyze(logs: dict[str, str] | None = None,
            runs_text: str | None = None, top: int = 10) -> CiReport:
    report = CiReport()
    if logs:
        report.clusters, report.error_events = cluster_logs(logs, top)
        report.logs_analyzed = len(logs)
    if runs_text and runs_text.strip():
        report.runs = analyze_runs(parse_runs(runs_text))
    return report


# ── CLI convenience: fetch runs metadata via the gh CLI ─────────────────────

def collect_gh_runs(repo: str, limit: int = 30) -> str:
    """Recent runs as our JSON shape, fetched with ``gh api`` (needs auth)."""
    import subprocess
    out = subprocess.run(
        ["gh", "api", f"repos/{repo}/actions/runs?per_page={limit}",
         "--jq", ("[.workflow_runs[] | {workflow: .name, "
                  "conclusion: .conclusion, head_sha: .head_sha, "
                  "run_number: .run_number, duration_s: "
                  "(((.updated_at | fromdate) - (.run_started_at | fromdate)))}]")],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "gh api failed")
    return out.stdout
