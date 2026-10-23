# Spec: Slim down frontend/ API clients (converge duplicated fetch/error handling)

Triage: `ready-for-agent`

## Problem Statement

As a frontend maintainer, every agent workspace's API client hand-rolls its HTTP plumbing. Eleven workspaces carry a byte-identical ~20-line "structured-error POST" block (fetch → parse `detail` → throw the legacy `ApiError(code, path, error)` or a plain `Error`), and two more workspaces (text2sql, seatunnel) plus stray calls elsewhere hand-roll plain-string error throwing that the shared `fetchJson` already implements. A fix to error parsing (e.g. a new detail shape from the backend) must be repeated in a dozen files, and the copies have already begun to drift in small ways.

## Solution

One shared HTTP layer. The shared api module gains a `postStructured` helper encapsulating the structured-error POST contract; the eleven workspaces call it instead of their local copies. The remaining plain-string fetch call sites adopt the existing shared `fetchJson`. Pages behave exactly as before — same requests, same localized error messages — but the contract lives in one place.

## User Stories

1. As a frontend maintainer, I want the structured-error POST contract defined once, so that a change to the backend's error detail shape is a one-edit fix.
2. As a frontend maintainer, I want all plain-JSON API calls to go through the shared fetchJson, so that non-2xx handling is uniform across workspaces.
3. As an agent developer adding a new workspace, I want to import `postStructured`/`fetchJson` rather than copy a block from a sibling, so that new api clients are a few lines each.
4. As a user of a page whose backend returns a structured error (e.g. bad_dir), I want the same localized error message as today, so that the refactor is invisible to me.
5. As a user of a page whose backend returns a plain detail string, I want the same error text surfaced as today, so that nothing regresses.
6. As a reviewer, I want each workspace's api client to contain only its endpoint paths, request/response types, and payload mapping, so that diffs show real contract changes.
7. As a maintainer, I want every touched workspace to pass its lint and build gates, so that the repo's per-workspace verification loop stays intact.
8. As a maintainer, I want the Playwright page tests for affected pages to stay green, so that error rendering is proven unchanged in a real browser.
9. As a maintainer, I want the copies deleted, not shadowed, so that no stale fetch block remains for future copy-paste.
10. As a maintainer, I want the legacy `(code, path, error)` ApiError constructor to keep working, so that the structured-error pages' catch-and-localize logic is untouched.
11. As a maintainer, I want call sites that only read `e.message` to keep working when a bare `Error` becomes an `ApiError`, so that the fetchJson adoption is behavior-preserving (ApiError extends Error with `message = detail`).
12. As a maintainer, I want the eleven-file conversion done mechanically with per-file review of catch sites, so that any workspace with genuinely divergent semantics is left alone and documented rather than force-converged.

## Implementation Decisions

- The shared api module is the single seam: it already owns `ApiError` (dual constructor, legacy `(code, path, error)` kept deliberately) and `fetchJson`; add `postStructured(url, body)` there, encoding the existing copied contract: POST JSON; on non-2xx parse `detail`; if detail is an object with `code`, throw legacy-shape ApiError; else throw with the string detail or `HTTP <status>`.
- `postStructured` reproduces the current block's behavior exactly (came from the 11 identical copies, which act as its prototype):
  on `!r.ok` → `detail = (await r.json().catch(() => ''))?.detail`; `typeof detail === 'object' && 'code' in detail` → `ApiError(d.code, d.path ?? '', d.error ?? '')`; otherwise `Error(detail || 'HTTP <status>')`.
- The eleven structured-error workspaces (change_impact, config_lint, config_migrate, dag_check, data_lineage, data_skew, metric_diff, pii_scan, schema_drift, sql_fmt, sql_transpile) replace their local blocks with `postStructured`; their exported function signatures, types, and endpoint paths do not change.
- text2sql and seatunnel adopt `fetchJson` for their plain-string fetches; GET/POST shape preserved via `init`. Converting a bare `Error` throw to `ApiError` is acceptable because `ApiError extends Error` and the pages read `message`; any call site that inspects the error beyond `message` is checked file-by-file during conversion.
- Streaming/SSE calls stay on the shared SSE helper; no changes there.
- No UI changes: no components, markup, styles, or i18n keys change.
- This continues the prior consolidation precedent (the earlier 4-workspace fetchJson adoption commit).

## Testing Decisions

- External behavior only: tests assert what pages render (reports, localized error banners), never which helper issued the fetch.
- Existing seams suffice — the Playwright page tests (`test_*_page.py`, driven by the shared conftest `make_page_url` factory) already exercise success and error paths of the affected pages end-to-end against the real FastAPI routers; they are the primary proof the refactor is invisible.
- Per-workspace gates: `npm run lint --workspace <name>` and `npm run build --workspace <name>` for every touched workspace (TypeScript compile proves the new helper's types line up).
- Suite-level: full pytest at batch close plus `seatunnel-agent ui --build` page smoke per repo rules; ticket-level runs are targeted page tests only.
- No new unit tests for `postStructured` itself unless a page test cannot cover a branch; behavior is already pinned by eleven pages' error-path tests.

## Out of Scope

- data_comparison's api client (478 lines — largest file, but it has bespoke session/SSE logic; not a mechanical dedupe).
- Any backend (src/) changes; the error contracts stay as-is.
- Migrating remaining Gradio pages, UI redesign, or i18n changes.
- Collapsing the dual ApiError constructor into one shape (would touch catch-site semantics; separate effort).
- The 6 pre-existing ruff findings in scripts/ (out of frontend scope).

## Further Notes

- Seam assumption (flagged for confirmation): the shared api module is the one seam; no new files unless the helper demands one.
- Estimated reduction: ~200 lines (structured block ×11) + ~60–90 lines (fetchJson adoption).
- Corresponds to 批次 F1/F2 of the frontend slim-down investigation (2026-10-23).
