# 02: Extract a router factory in common/

**What to build:** A `make_agent_router()` function in `seatunnel_agent.common.api_factory` that takes a prefix, domain function, and request model and returns a fully wired APIRouter with health endpoint, timing, path validation, and error handling. One standard-shaped agent's api.py (metric_diff) is migrated to the factory as proof. Existing tests pass; factory has its own unit tests with a fake domain function.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] `seatunnel_agent.common.api_factory` module exists with `make_agent_router()`
- [ ] Factory handles: timing (elapsed_ms), path whitelist validation, try/except with structured error detail, health endpoint, normalize_lang
- [ ] `metric_diff/api.py` uses the factory (≤15 lines of config)
- [ ] All existing metric_diff API tests pass unchanged
- [ ] Factory has unit tests with a fake domain function covering: success, bad path (403), domain error (400), health
- [ ] `ruff check` and `mypy` pass
