# 04: Close the registry loop — auto-mount React routers from manifests

**What to build:** `AgentManifest` gains a `router` field. `ui.py` loops over discovered manifests to mount routers instead of 15 hand-coded `include_router` blocks. The ~90 lines of manual wiring are deleted. Registry unit tests verify router mounting. All page and API tests pass.

**Blocked by:** 02 (router factory — manifests need to reference factory-built routers).

**Status:** ready-for-agent

- [ ] `AgentManifest` has an optional `router: str | None` field (lazy import string)
- [ ] Each agent's manifest.py declares its router
- [ ] `ui.py` loops `for mf in discover(): if mf.router: app.include_router(resolve(mf.router))`
- [ ] All 15 manual `include_router` blocks in ui.py are deleted
- [ ] Registry unit tests verify that manifests with `router` fields get their routers mounted
- [ ] All existing page and API tests pass
- [ ] `ruff check` and `mypy` pass
