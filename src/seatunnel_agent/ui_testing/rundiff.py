"""Cross-run comparison: which cases changed verdict between two runs.

Used by the ``compare`` CLI subcommand and the "vs previous run" section of
the HTML report.  A run is the ``result.json`` inside a ``runs/<ts>/`` dir.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

RUNS_DIR = Path("runs")


@dataclass
class CaseDelta:
    case_id: str
    title: str
    old: str            # verdict in the older run ("-" if absent)
    new: str            # verdict in the newer run
    old_ms: int
    new_ms: int

    @property
    def regressed(self) -> bool:
        return self.new in ("FAIL", "ERROR") and self.old == "PASS"

    @property
    def recovered(self) -> bool:
        return self.new == "PASS" and self.old in ("FAIL", "ERROR")


@dataclass
class RunDiff:
    old_run: str
    new_run: str
    changed: list[CaseDelta]
    slower: list[CaseDelta]      # >2x and >3s elapsed growth

    @property
    def regressions(self) -> list[CaseDelta]:
        return [d for d in self.changed if d.regressed]


def _load(path: Path) -> dict:
    return json.loads((path / "result.json").read_text(encoding="utf-8"))


def list_runs(runs_dir: Path = RUNS_DIR) -> list[Path]:
    """Run dirs that contain a result.json, oldest first."""
    if not runs_dir.is_dir():
        return []
    return sorted(d for d in runs_dir.iterdir()
                  if d.is_dir() and (d / "result.json").is_file())


def previous_run_with_suite(suite: str, before: str,
                            runs_dir: Path = RUNS_DIR) -> Path | None:
    """The most recent earlier run of the same suite (for report context)."""
    for d in reversed(list_runs(runs_dir)):
        if d.name >= before:
            continue
        try:
            if _load(d).get("suite") == suite:
                return d
        except (OSError, json.JSONDecodeError):
            continue
    return None


def diff_runs(old_dir: Path, new_dir: Path) -> RunDiff:
    old_doc, new_doc = _load(old_dir), _load(new_dir)
    old_by = {c["case_id"]: c for c in old_doc["cases"]}
    changed: list[CaseDelta] = []
    slower: list[CaseDelta] = []
    for c in new_doc["cases"]:
        o = old_by.get(c["case_id"])
        delta = CaseDelta(
            case_id=c["case_id"], title=c.get("title", ""),
            old=o["verdict"] if o else "-", new=c["verdict"],
            old_ms=o.get("elapsed_ms", 0) if o else 0,
            new_ms=c.get("elapsed_ms", 0),
        )
        if delta.old != delta.new:
            changed.append(delta)
        elif (o and delta.new == "PASS" and delta.old_ms > 0
                and delta.new_ms > max(2 * delta.old_ms, delta.old_ms + 3000)):
            slower.append(delta)
    return RunDiff(old_run=old_dir.name, new_run=new_dir.name,
                   changed=changed, slower=slower)


def format_diff(d: RunDiff) -> str:
    lines = [f"对比: {d.old_run} → {d.new_run}"]
    if not d.changed and not d.slower:
        lines.append("verdict 无变化,无明显变慢。")
        return "\n".join(lines)
    for c in d.changed:
        mark = "🔴 回归" if c.regressed else ("🟢 恢复" if c.recovered else "↔ 变化")
        lines.append(f"{mark}  {c.case_id:<5} {c.old} → {c.new}  {c.title}")
    for c in d.slower:
        lines.append(f"🐢 变慢  {c.case_id:<5} "
                     f"{c.old_ms / 1000:.1f}s → {c.new_ms / 1000:.1f}s  {c.title}")
    return "\n".join(lines)
