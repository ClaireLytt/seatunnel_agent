# 04: Session management — new / list / load / rename / delete

**What to build:** The sidebar lists past sessions (backed by the existing common history module, storage format unchanged). The user can start a new chat, switch to an old session and see its messages restored, rename a session, and delete one. Sidebar collapse/expand toggle works.

**Blocked by:** 02 — Chat round-trip

**Status:** done

- [x] New chat resets the conversation and appears in history after first exchange
- [x] Selecting a history entry restores its messages into the chat area
- [x] Rename and delete round-trip through the API and update the list
- [x] In-process API tests cover session CRUD
- [x] ruff/mypy/pytest + workspace lint/build green
