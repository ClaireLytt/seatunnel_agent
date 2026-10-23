# Architecture Deduplication — 6 Deepening Candidates

**Label:** `ready-for-agent`

## Problem Statement

After migrating 30+ agent pages to React, the codebase has accumulated significant duplication across three layers: frontend workspace boilerplate (7 identical config files × 30 workspaces), backend API boilerplate (hand-rolled error handling / health checks in every api.py), and frontend fetch error handling (copy-pasted in every api.ts). Additionally, agent titles are defined in 3 places, a domain-specific module lives in the wrong package, and a vestigial manifest field adds noise.

## Solution

Six targeted deepening passes to improve leverage and locality:
1. Frontend workspace generator + hoisted devDeps
2. Backend API composable pieces
3. Frontend api.ts migration to shared fetchJson
4. i18n title single-source-of-truth
5. Move connector_docs.py to its domain
6. Clean up vestigial manifest render field

## User Stories

1. As a developer adding a new agent, I want to run one command to scaffold the frontend workspace, so I don't copy 7 boilerplate files.
2. As a developer bumping a dependency version, I want to edit one file instead of 30+ package.json files, so version drift is impossible.
3. As a developer writing a new backend API, I want to compose shared pieces (health check, error response, path guard) instead of hand-rolling boilerplate.
4. As a developer writing a frontend api.ts, I want to use a shared fetchJson helper so error handling is consistent and I write less code.
5. As a developer renaming an agent, I want to change the title in one place (manifest.py) and have it propagate to the hub card and the React page.
6. As a developer reading the config_lint code, I want connector_docs.py co-located with its primary consumer, not buried in common/.
7. As a developer creating a React agent manifest, I want to skip the render="" field since it's meaningless for external pages.
8. As a maintainer, I want consistent error contracts across all frontend workspaces so debugging API failures is predictable.
9. As a maintainer, I want the unused api_factory.py either adopted or deleted so it doesn't mislead future developers.

## Implementation Decisions

### Candidate 1: Frontend Workspace Generator
- Hoist all shared devDependencies to root `frontend/package.json`. Individual workspace package.json files keep only `name`, `version`, `type`, `scripts`, and workspace-specific deps (e.g. recharts, mermaid).
- The 1-line re-export files (eslint.config.js, postcss.config.js, tailwind.config.ts) stay as-is — they're already minimal and npm workspaces can't inherit these.
- tsconfig trio stays as-is — they extend shared bases and the per-workspace tsBuildInfoFile path is required by TypeScript.
- A `scripts/new-workspace.py` generator creates the scaffold: takes `--name` and `--route`, produces vite.config.ts, index.html, src/main.tsx, src/index.css, src/vite-env.d.ts, and stub src/App.tsx + src/i18n.ts + src/api.ts.
- The generator also adds the workspace to `frontend/package.json` workspaces array.

### Candidate 2: Backend API Composable Pieces
- Keep the existing `add_health`, `ms_since`, `require_dir` in `api_guard.py` — they're already adopted.
- Add a `standard_error_detail` helper that extracts FastAPI error detail in a consistent format.
- Evaluate whether `api_factory.py` should be deleted (if truly unused) or updated to use the composable pieces internally.

### Candidate 3: Frontend fetchJson Adoption
- The shared `fetchJson` in `@shared/api.ts` already exists. Migrate the 25+ workspaces that hand-roll fetch+error to use it instead.
- This is a mechanical find-and-replace: each hand-rolled `fetch` + error block becomes a `fetchJson` call.

### Candidate 4: i18n Title Single Source
- Add a `GET /api/meta` endpoint (or embed manifest data as a JSON `<script>` block in the served HTML) so the React page reads title/subtitle from the manifest instead of duplicating them in i18n.ts.
- Keep i18n.ts for UI-chrome keys (button labels, placeholders) — only titles move.

### Candidate 5: Move connector_docs.py
- Move from `common/connector_docs.py` to the config_lint agent package or a shared domain package. Update all import paths.

### Candidate 6: Manifest render Default
- Make `render` field default to `""` in the AgentManifest dataclass. Remove explicit `render=""` from all external=True manifests. Once MCP Toolbox migrates, consider removing the field entirely.

## Testing Decisions

- **Candidate 1**: Test the generator script — run it, verify the produced workspace builds (`npm run build`) and lints. Existing workspaces should continue to build after devDep hoisting.
- **Candidate 2**: Existing backend tests cover the API endpoints. No new tests needed unless new helpers are added — then unit test those.
- **Candidate 3**: Existing Playwright page tests verify the full fetch→render flow. A mechanical migration to fetchJson should not break them.
- **Candidate 4**: The i18n parity tests would be simplified (fewer keys to check). The meta endpoint gets a simple integration test.
- **Candidate 5**: `ruff check` + `pytest` — import paths must resolve. Existing config_lint tests are the verification.
- **Candidate 6**: `tests/test_registry.py` already verifies manifest discovery. No new tests needed.

## Out of Scope

- No new features — this is purely internal architecture improvement.
- No changes to the MCP Toolbox page (the last Gradio page).
- No changes to the hub landing page design.
- No backend i18n pattern standardization (worth doing but separate).

## Further Notes

- Candidates are independent — they can be done in any order.
- Candidate 1 has the highest daily impact and lowest risk.
- Candidate 3 is the most mechanical (find-and-replace).
- Candidate 4 is the most architecturally interesting but has the widest blast radius.
