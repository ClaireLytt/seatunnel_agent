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


# ── cross-run flaky trend (mined from runs/history.jsonl) ──

def load_history(runs_dir: Path = RUNS_DIR,
                 last: int = 0) -> list[dict]:
    """Parsed history.jsonl records, oldest first; corrupt lines skipped."""
    path = Path(runs_dir) / "history.jsonl"
    if not path.is_file():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec.get("verdicts"), dict):
            records.append(rec)
    return records[-last:] if last else records


def flaky_trend(records: list[dict]) -> list[dict]:
    """Per-case verdict stability across runs, most unstable first.

    SKIP/MANUAL don't count as signal (a --no-llm run skipping ai cases is
    expected, not flaky); a case is flaky when it produced more than one
    distinct executed verdict (PASS/FAIL/ERROR) across the window."""
    per_case: dict[str, list[tuple[str, str]]] = {}
    for rec in records:
        for cid, verdict in rec["verdicts"].items():
            if verdict in ("PASS", "FAIL", "ERROR"):
                per_case.setdefault(cid, []).append((rec["ts"], verdict))
    rows: list[dict] = []
    for cid, hits in per_case.items():
        verdicts = [v for _, v in hits]
        distinct = set(verdicts)
        fails = sum(1 for v in verdicts if v != "PASS")
        rows.append({
            "case_id": cid,
            "runs": len(verdicts),
            "fails": fails,
            "fail_rate": fails / len(verdicts),
            "flaky": len(distinct) > 1,
            "last": verdicts[-1],
        })
    rows.sort(key=lambda r: (not r["flaky"], -r["fail_rate"], r["case_id"]))
    return rows


def format_trend(rows: list[dict], runs_seen: int) -> str:
    if not rows:
        return "runs/history.jsonl 为空 — 先跑几轮再看趋势。"
    lines = [f"—— 近 {runs_seen} 轮 verdict 趋势 ——",
             f"{'用例':<8}{'执行':<6}{'非PASS':<8}{'失败率':<9}{'最近':<7}标记"]
    for r in rows:
        if not r["flaky"] and r["fails"] == 0:
            continue
        mark = "🌪 FLAKY" if r["flaky"] else ""
        lines.append(f"{r['case_id']:<8}{r['runs']:<6}{r['fails']:<8}"
                     f"{r['fail_rate']:<9.0%}{r['last']:<7}{mark}")
    if len(lines) == 2:
        lines.append("(全部用例在窗口内稳定 PASS ✅)")
    stable = sum(1 for r in rows if not r["flaky"] and r["fails"] == 0)
    lines.append(f"稳定 {stable} / 覆盖 {len(rows)} 用例")
    return "\n".join(lines)
