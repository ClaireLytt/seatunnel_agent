# 04: Migrate data_lineage onto the shared loop

**What to build:** Lineage Q&A answers identically (per-question state reset preserved); the hand-rolled `_agent_loop` is deleted and replaced by ToolLoopAgent with lineage's tools and prompts.

**Blocked by:** 01 (Expand: grow ToolLoopAgent's interface).

**Status:** done (2026-10-23)

- [x] Local loop deleted; existing lineage API/agent tests green unchanged
- [x] One offline loop test added (scripted client)
- [x] ruff/mypy + targeted tests green

