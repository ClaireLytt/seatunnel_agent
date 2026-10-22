# 02: React workspace + working form → report flow

**What to build:** A new `frontend/dep_check/` Vite + React 18 + TS + Tailwind workspace using `@shared` components. The page renders at `/depcheck` with:
- Left sidebar: textarea for pasting pyproject.toml/requirements.txt, "Analyze" (primary), "Check this project" (secondary), "Clear" (ghost)
- Right main area: `ReportView` showing the Markdown report
- i18n (en/zh) via st-lang cookie
- Loading spinner and error states
- Manifest updated to `external=True`, `render=""`

The page is demoable end-to-end after this ticket.

**Blocked by:** 01 (needs check-self endpoint)

**Status:** ready-for-agent

- [ ] `frontend/dep_check/` workspace builds (`npm run build`)
- [ ] Page loads at `/depcheck` with PageHeader, Card, sidebar + main layout
- [ ] Paste text + Analyze → report rendered via ReportView
- [ ] "Check this project" → calls check-self endpoint → report
- [ ] Clear resets form and report
- [ ] Language toggle works (en/zh)
- [ ] Loading and error states shown
- [ ] Responsive: stacks on narrow screens
- [ ] Manifest updated, hub serves React dist
- [ ] `npm run lint` passes
