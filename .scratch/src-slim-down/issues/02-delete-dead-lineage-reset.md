# 02: Delete the lineage agent's uncalled reset method

**What to build:** The data lineage agent no longer carries a `reset()` method that nothing in src or tests calls; behavior is unchanged everywhere.

**Blocked by:** None (can start immediately).

**Status:** done (2026-10-23)

- [x] The method is deleted; grep confirms no caller existed
- [x] Lineage tests green; ruff/mypy pass
