# 06: Chat export

**What to build:** The user clicks Export in the sidebar and downloads a zip archive of the current session's chat, equivalent to the legacy page's export.

**Blocked by:** 04 — Session management

**Status:** ready-for-agent

- [ ] Export downloads a valid zip containing the current session's chat content
- [ ] In-process API test asserts the zip is well-formed and non-empty for a session with messages
- [ ] ruff/mypy/pytest + workspace lint/build green
