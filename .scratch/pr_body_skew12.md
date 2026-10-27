for #21 (data skew) — follow-up to #145

## Summary

The static skew detector gets the same quality instrument the text2sql line has in `t2s-bench`: a labeled corpus and a gateable benchmark.

```text
examples/skew_bench/cases.yaml      # 23 curated cases: all 13 rules covered
                                    # + clean negatives; expectations are
                                    # EXACT sets, reviewed case by case
                                    # (not recorded snapshots); baseline.min_f1

agents/data/data_skew/bench.py      # micro precision/recall/F1 +
                                    # per-case missed/spurious diffs, zh/en

seatunnel-agent skew-bench [--corpus F] [--gate] [-F json]
                                    # scorecard; --gate exits 1 below min_f1
```

A pytest guard (`test_bench_corpus_is_green`) turns any whole-corpus behavior shift from a rule tweak into a red test with a per-case diff.

## Evidence

- **Before:** the 13 static rules had per-rule unit tests but no whole-corpus scorecard — a tweak's net precision/recall effect was invisible.
  **After:** live run: `23 cases · precision 1.000 · recall 1.000 · F1 1.000 (gate 1.000)`; CLI tests cover the green gate, a failing corpus (exit 1 with the per-case diff) and parseable JSON. `tests/test_data_skew.py` 212 -> 215 passed; full `pytest -q` -> **3520 passed, 1 skipped**; ruff clean; mypy Success (175 files).
- Curation notes live in the corpus comments (e.g. why `rand-in-join` expects DS012 without DS008).
- Batch reports: `docs/reports/20261028-skew-bench-{core,cli}.md`.

## Merge Danger

**Door:** two-way

New module, corpus and command; no existing behavior changes.

**Blast Radius:** minimal

Future detector-rule PRs must keep the corpus green or consciously update expectations — that friction is the point.
