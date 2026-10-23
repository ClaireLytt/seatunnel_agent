# 03: Migrate sql_review onto the shared loop

**What to build:** SQL review's LLM pass produces identical reviews; its hand-rolled `_agent_loop` is deleted and replaced by ToolLoopAgent with sql_review's tools and prompts.

**Blocked by:** 01 (Expand: grow ToolLoopAgent's interface).

**Status:** done (2026-10-23)

- [x] Local loop deleted; behavior anchored by existing sql_review tests green unchanged
- [x] One offline loop test added (scripted client)
- [x] ruff/mypy + targeted tests green

