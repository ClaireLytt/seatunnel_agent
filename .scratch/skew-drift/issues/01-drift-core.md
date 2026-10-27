# 01: Drift core — baseline comparison over splitkey history

**What to build:** Given a table's splitkey patrol history, the agent can say
"drift / stable / insufficient" for the configured key: the latest measurement
is compared against the median of earlier ones, and any metric that worsened
past threshold (top-1 concentration +10 pp, NULL share +5 pp, NDV −30 %) is
reported with baseline, current value and delta. Verifiable on its own through
unit tests over synthetic history records — the single seam everything later
consumes.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Fewer than 3 measured records → verdict `insufficient`, never `stable`
- [ ] Stable history → `stable` with no metric drifts
- [ ] Top-1 rise, NULL rise and NDV collapse each produce a drift with correct baseline/current/delta
- [ ] Records without measured metrics are ignored, not counted toward history depth
- [ ] `pytest tests/test_data_skew.py -q` tail shows `passed`; `ruff` + `mypy` clean
