# 03: Connect & setup controls

**What to build:** The sidebar's configuration block works end-to-end: mode selector, config-path input, template selector, Connect button, and a status readout that reflects the backend's real connection result.

**Blocked by:** 01 — Walking skeleton

**Status:** ready-for-agent

- [ ] Mode/template options come from the meta API; config path is editable
- [ ] Connect calls the backend and the status box shows the genuine result (success and failure)
- [ ] In-process API test covers connect success/failure contract
- [ ] ruff/mypy/pytest + workspace lint/build green
