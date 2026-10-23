# 02: Migrate the orchestrator onto the shared loop

**What to build:** The orchestrator answers end-to-end requests exactly as today — same steps surfaced, same report, same truncation semantics — but its hand-rolled loop body (the drifted original the shared loop was generalized from) is deleted and replaced by ToolLoopAgent, and its duplicate Step/Result dataclasses are deleted in favor of the shared schema.

**Blocked by:** 01 (Expand: grow ToolLoopAgent's interface).

**Status:** ready-for-agent

- [ ] Orchestrator's local loop and duplicate dataclasses deleted (replace, don't layer)
- [ ] Existing orchestrator API/telemetry tests green unchanged
- [ ] One offline loop test added (orchestrator tools + scripted client)
- [ ] ruff/mypy + targeted tests green

