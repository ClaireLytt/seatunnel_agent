# -*- coding: utf-8 -*-
"""Stability check: N consecutive smoke rounds must produce identical verdicts."""
import io
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10

baseline = None
for i in range(1, N + 1):
    r = subprocess.run(
        [sys.executable, "-m", "seatunnel_agent.ui_testing", "run",
         "--suite", "smoke", "--no-llm"],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=900)
    verdicts = {}
    for line in (r.stdout or "").splitlines():
        for v in ("PASS", "FAIL", "ERROR", "SKIP"):
            if line.strip().startswith(("✅", "❌", "💥", "⏭")) and f" {v} " in f" {line} ":
                parts = line.split()
                # e.g. "✅ PASS   A4    title..."
                if len(parts) >= 3 and parts[1] == v:
                    verdicts[parts[2]] = v
    sig = tuple(sorted(verdicts.items()))
    status = "identical" if sig == baseline else ("baseline" if baseline is None else "DIFFERENT!")
    print(f"round {i}: exit={r.returncode} cases={len(verdicts)} -> {status}", flush=True)
    if baseline is None:
        baseline = sig
    elif sig != baseline:
        old = dict(baseline)
        for k, v in sorted(verdicts.items()):
            if old.get(k) != v:
                print(f"  drift: {k}: {old.get(k)} -> {v}", flush=True)
        sys.exit(1)
print(f"\n{N} consecutive smoke rounds identical — no flaky cases.")
