# 05: Migrate text2sql onto the shared loop (event protocol via the event seam)

**What to build:** A text2sql chat question streams the same events to the page (deltas, tool calls, result tables, final) — but the agent's hand-rolled loop is deleted; its on_event/result protocol and few-shot augmentation live in the agent as consumers of the shared loop's event seam and hint hook.

**Blocked by:** 01, 02 (first migration must prove the seams before a live chat surface moves).

**Status:** done (2026-10-23)

- [x] Local loop deleted; event protocol preserved through the loop's event callback (any semantic that can't be hosted cleanly is documented, not forced)
- [x] Existing text2sql tests + Playwright stream-flow page tests green unchanged
- [x] One offline loop test added (scripted client)
- [x] ruff/mypy + targeted tests green

