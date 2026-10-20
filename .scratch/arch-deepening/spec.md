# Spec: Deepen seatunnel_agent architecture

## Problem Statement

The seatunnel_agent codebase has grown to 15+ agents, each following the same pattern (manifest, api.py, frontend workspace). Three areas of shallow-module friction have emerged:

1. **Frontend duplication** — 13 identical ReportView components, 15 identical ApiError classes, duplicated DIALECTS arrays and CSS constants across workspaces; the `@shared` package contains only `Card`.
2. **Shallow api.py modules** — every agent's api.py repeats the same Request/Response/handler skeleton (~70-100 lines each), differing only in the domain function call.
3. **Manual router wiring** — `ui.py` contains 15 hand-coded `include_router` blocks that bypass the auto-discovery system in `registry.py`.

## Solution

1. Deepen `@shared` by absorbing duplicated frontend modules (ReportView, ApiError, DIALECTS, CSS constants).
2. Extract a router factory in `common/` that generates the boilerplate api.py skeleton from config.
3. Extend `AgentManifest` with a `router` field so the registry auto-mounts React backend routers.
4. Combine 2+3 so adding a standard agent requires only a manifest — no api.py, no ui.py edit.

## User Stories

1. As a developer adding a new agent, I want to declare only a manifest.py, so that I don't have to copy-paste api.py boilerplate and edit ui.py.
2. As a developer fixing a bug in report rendering, I want to fix it in one place (@shared/ReportView), so that all 13 workspaces get the fix.
3. As a developer fixing API error handling, I want the try/except/timing logic in one factory, so that a fix applies to all 15 agents.
4. As a developer building a new React workspace, I want to import ReportView, ApiError, fetchAgent, and DIALECTS from @shared, so that I start with imports not copy-paste.
5. As a maintainer reading ui.py, I want to see a 3-line loop instead of 90 lines of imports, so that the wiring logic is obvious.

## Implementation Decisions

- Router factory lives in `seatunnel_agent.common.api_factory` (new module).
- Factory signature: `make_agent_router(prefix, tags, domain_fn, request_model, *, allowed_dirs_env, health_name)` → `APIRouter`.
- Non-standard agents (multi-endpoint, SSE, dual-mode input like schema_drift) keep a custom api.py that can extend or bypass the factory.
- `AgentManifest` gains an optional `router: str | None` field (lazy import string like `"pkg.module:router"`).
- Frontend shared modules go into `@shared/components/` (ReportView), `@shared/api/` (ApiError, fetchAgent), `@shared/constants/` (DIALECTS, CSS classes).

## Testing Decisions

- Router factory tested with a fake domain function — assert correct status codes, timing, health endpoint, path validation errors.
- Registry auto-mount tested by adding a manifest with `router` field and asserting it appears in app routes.
- Frontend: all workspaces must build (`npm run build --workspaces`); shared modules get vitest unit tests.
- Prior art: existing `tests/test_registry.py`, existing per-agent API tests (`tests/test_*_page.py`).

## Out of Scope

- Redesigning the agent domain logic (differ.py, checker.py, scanner.py).
- Changing the Gradio → React migration pattern itself.
- Adding new agents.

## Further Notes

Seams: AgentManifest (existing), @shared exports (existing), router factory (new internal seam in common/).
