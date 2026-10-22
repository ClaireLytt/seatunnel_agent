# 01: Backend — add check-self endpoint

**What to build:** A `GET /api/depcheck/check-self?lang=zh` endpoint that runs `collect_from_path(".") → check → render_markdown` and returns the same `CheckResponse` shape as the existing `POST /check`. This is the only backend addition needed for the React page's "Check this project" button.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `GET /api/depcheck/check-self` endpoint exists and returns `CheckResponse`
- [ ] Accepts optional `lang` query param (default `zh`)
- [ ] Returns 200 with result + markdown report
- [ ] ruff + mypy pass
- [ ] Existing dep_check tests still pass
