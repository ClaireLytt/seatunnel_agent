# Spec: SQL Review page — visual alignment with the uitest page

Labels: ready-for-agent
Branch: seatunnel-react-migration (user-confirmed: stay on the current branch, no new branch)

## Problem Statement

The SQL Review React page and the UI-test React page share the engineering-paper design system but diverge in small visual conventions. A user moving between the pages sees a trend chart whose severity colors ignore the theme (and break in dark mode), a permanently-rendered empty report card where the uitest page hides empty sections, errors shown as plain colored text where the uitest page marks them with a ❌ glyph, and an untranslated input label.

## Solution

Bring the SQL Review page's visual conventions in line with the uitest page in four scoped touches, with no functional change: theme-token chart colors, hide-when-empty report section, ❌-prefixed error messages, and the hardcoded label moved into the i18n dictionaries.

## User Stories

1. As a dark-mode user, I want the review trend chart's severity colors to come from the theme tokens, so that the chart stays legible and consistent when the theme inverts.
2. As a user of both pages, I want the trend chart and the uitest counts chart to speak the same color vocabulary (accent for bad, ok for good, neutral for middle), so that severity reads the same across the product.
3. As a first-time visitor, I want the report section hidden until a report exists, so that the page shows only meaningful content (matching the uitest page's empty-state behavior).
4. As a user whose review fails, I want the error message marked with the same ❌ convention the uitest page uses, so that failures are instantly recognizable.
5. As a Chinese-speaking user, I want the SQL input label localized like every other label on the page, so that the page has no stray hardcoded strings.
6. As a maintainer, I want the now-unused report-placeholder i18n strings removed in the same change, so that no dead keys linger.
7. As a maintainer, I want these changes verified by the page's existing browser test plus before/after screenshots, so that the visual change is reviewable.

## Implementation Decisions

- Scope is exactly the four items the user circled (1-4 of the comparison list); items 5 (SSE progress) and 6 (per-review history) are explicitly deferred.
- Work lands on the current integration branch, not a new branch (user-confirmed).
- Chart severity palette maps to existing theme tokens only — critical→accent, suggestion→ok, risk→the neutral soft-ink token — following the uitest counts chart precedent; no new tokens are introduced.
- Empty-state: the report section (heading and card) renders only when a report exists, mirroring the uitest page's conditional sections; the placeholder strings are deleted from both locale dictionaries.
- Error presentation: prepend the ❌ glyph to the error text at render time (and the stats accordion's error line for consistency within the page); wording unchanged.
- The SQL input label becomes an i18n key in both locales ("SQL" in both, matching the dialect-label convention of keeping technical terms untranslated).
- The page badge text stays hardcoded: all three React pages share that convention; changing it is out of scope.
- No backend, API, or shared-package changes.

## Testing Decisions

- Good tests assert what a real browser shows, not component internals.
- Seam (single, pre-existing): the Playwright page test for the SQL Review page (in-process uvicorn, same pattern as the other React page tests) — extend it minimally to cover the report section being absent before a review.
- Chart colors and glyph prefixes are visual conventions verified by before/after screenshots under the reports shots directory (per the project's UI-change verification rule), not by DOM assertions.
- Full local gate per project rules: ruff, pytest, frontend lint + build for the sql_review workspace.

## Out of Scope

- SSE streaming progress for agent-mode review (item 5) and per-review history (item 6) — deferred, likely a follow-up spec.
- Reusing Collapsible inside the uitest page (a uitest-side cleanup, not this page).
- Badge/breadcrumb i18n, layout changes, or any functional behavior change.

## Further Notes

- The comparison evidence (file:line divergence list) came from the exploration pass comparing the two workspaces; the four items were individually circled by the user, who also chose to keep items 5-6 out.
