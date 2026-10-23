# Spec: Slim down src/ (single-source the bad_dir guard; remove dead code)

Triage: `ready-for-agent`

## Problem Statement

As a backend maintainer, the directory-input guard — path whitelist check followed by "directory exists" check that raises the structured `bad_dir` error the React pages localize — is copy-pasted across seven agent API routers (config_lint, config_migrate, dag_check, data_lineage, pii_scan, sql_fmt, sql_transpile). One of them (data_lineage) even wraps it in its own local helper, proving the abstraction wants to exist. A change to the guard contract (e.g. the error detail shape, or the 403/400 split) must be repeated seven times. Separately, the data lineage agent carries a `reset()` method with no caller in src or tests.

## Solution

One shared guard. The common api_guard module (which already owns `check_path_allowed`) gains `require_dir(path, env_var)`: whitelist first (403, no existence probing), then existence (400 with structured `{code: "bad_dir", path}`). The seven routers call it; the dead method is deleted. API responses are byte-identical.

## User Stories

1. As a backend maintainer, I want the bad_dir guard defined once next to the whitelist check, so that a contract change is a one-edit fix.
2. As a frontend maintainer, I want every directory-taking endpoint to emit the identical structured `bad_dir` detail, so that the shared postStructured/ApiError path localizes all of them uniformly.
3. As a security reviewer, I want the whitelist-before-existence ordering encoded in one function, so that no router can accidentally probe path existence before authorization.
4. As an agent developer adding a directory-taking endpoint, I want to call one guard, so that I cannot get the ordering or the detail shape wrong.
5. As a user submitting a non-existent directory, I want the same localized error as today, so that the refactor is invisible.
6. As a user submitting a path outside the allowlist, I want the same 403 as today, so that nothing regresses.
7. As a maintainer, I want the data_lineage local helper replaced by the shared one, so that there is exactly one implementation.
8. As a maintainer, I want the uncalled lineage agent reset method deleted, so that dead code stops suggesting an API that nothing uses.
9. As a maintainer, I want ruff/mypy and the seven agents' API tests green, so that the change is proven behavior-preserving.
10. As a reviewer, I want each router's diff to show only the guard call replacing the inline block, so that review is mechanical.

## Implementation Decisions

- The common api_guard module is the single seam; `require_dir(raw_path, env_var)` lives beside `check_path_allowed` and calls it first, then raises the structured 400. Signature mirrors `check_path_allowed` (path + env var naming the per-agent allowlist; keep the noun parameter only if a caller needs it).
- The shape is already proven by data_lineage's local `_require_dir` (its body is the exact contract; treat it as the prototype): whitelist check → `is_dir()` → `HTTPException(400, {"code": "bad_dir", "path": d})`.
- Seven routers swap their inline blocks/local helper for the shared guard; endpoint signatures, response models, and error payloads unchanged.
- Variants that pass extra keys in the detail (if any surface during conversion) are left inline and documented rather than force-converged.
- Delete the lineage agent's uncalled reset method; no replacement.
- No frontend changes; the frontend contract (postStructured) is already converged.

## Testing Decisions

- External behavior only: the proof is each agent's existing API tests (FastAPI TestClient) asserting 403 for non-allowlisted paths and the structured 400 `bad_dir` detail for missing dirs — those tests already exist per agent and must stay green unchanged.
- No new tests for `require_dir` itself unless an agent lacks coverage of one branch; prefer adding the missing case to that agent's API test file (prior art: existing bad_dir assertions in the agents' test files).
- Ticket-level: ruff/mypy + the seven agents' test files; batch close: full pytest per repo rules.

## Out of Scope

- Splitting oversized files (comparator.py et al.) — separate plan/approval.
- The three frontend workspaces with divergent ApiError semantics (change_impact/data_lineage/data_skew client-side) — needs a contract-unification spec.
- Any change to the whitelist semantics (403 behavior, env var names).
- The vulture 60%-confidence list (verified false positives).

## Further Notes

- Seam assumption (flagged for confirmation): common api_guard is the one seam; no new module.
- Estimated reduction: ~30–40 lines; main value is contract single-sourcing, not line count.
- Corresponds to 批次 S1 of the src slim-down investigation (2026-10-23).
