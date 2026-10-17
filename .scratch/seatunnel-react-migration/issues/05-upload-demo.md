# 05: Upload + demo mode

**What to build:** The user can attach a file to the conversation via an upload control, and run the built-in Demo flow which streams its scripted steps into the chat (preserving the step-delay environment-variable behaviour).

**Blocked by:** 02 — Chat round-trip

**Status:** done

- [x] Uploaded file reaches the agent and is referenced in the conversation
- [x] Demo button streams the demo steps into the chat exactly as the legacy page did
- [x] In-process API tests cover upload and demo endpoints
- [x] ruff/mypy/pytest + workspace lint/build green
