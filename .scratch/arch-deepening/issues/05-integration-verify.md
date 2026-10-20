# 05: Integrate and verify — manifest-driven agent wiring end-to-end

**What to build:** End-to-end smoke test that proves adding a new agent requires only manifest.py. A test adds a dummy agent manifest (with domain function ref and request model) and verifies it appears on the hub and responds to API calls. All tests pass.

**Blocked by:** 03 (migrate api.py), 04 (registry auto-mount).

**Status:** ready-for-agent

- [ ] Smoke test: register a dummy manifest with `router` field, verify hub card appears and API endpoint responds
- [ ] Full test suite passes (`pytest`)
- [ ] Frontend builds pass (`npm run build --workspaces`)
- [ ] `ruff check` and `mypy` pass
