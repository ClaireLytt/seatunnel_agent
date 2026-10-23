# 04: Migrate data_lineage onto the shared loop

**What to build:** Lineage Q&A answers identically (per-question state reset preserved); the hand-rolled `_agent_loop` is deleted and replaced by ToolLoopAgent with lineage's tools and prompts.

**Blocked by:** 01 (Expand: grow ToolLoopAgent's interface).

**Status:** ready-for-agent

- [ ] Local loop deleted; existing lineage API/agent tests green unchanged
- [ ] One offline loop test added (scripted client)
- [ ] ruff/mypy + targeted tests green

