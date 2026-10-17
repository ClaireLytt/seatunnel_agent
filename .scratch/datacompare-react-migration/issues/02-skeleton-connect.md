# 02: Walking skeleton — React page at /datacompare with dual-source connect

**What to build:** The route serves a React SPA (wide sidebar + results panel shell, engineering-paper theme). Source A and source B each have a connection form (datasource type with type-appropriate field visibility, host/port/db/user/password), a Connect button, a live status readout and a table picker fed by the real connection — all through the new REST namespace and the session registry.

**Blocked by:** 01 — Prefactor

**Status:** ready-for-agent

- [ ] Browser renders the React shell; legacy Gradio no longer serves the route (code remains until ticket 11)
- [ ] Connect A and B independently; statuses and table dropdowns reflect real connections
- [ ] Field visibility follows datasource type like legacy
- [ ] In-process API tests: connect success/failure per side, tables listing
- [ ] Playwright smoke: page loads, no console errors
- [ ] Project verification commands green
