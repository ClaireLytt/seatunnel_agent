# 01: Walking skeleton — React page live at /seatunnel

**What to build:** Opening the SeaTunnel Pipeline Builder route in a real browser serves a new React SPA (engineering-paper theme: header, topbar, empty sidebar + chat layout shell) instead of the Gradio page. A meta endpoint under the page's API namespace answers with the page's static metadata (modes, templates). The workspace is cloned from the uitest skeleton, registered in the npm workspaces, built, and statically mounted via the manifest's external mount; the unbuilt-dist hint fallback works.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Browser at the /seatunnel route renders the React shell (shared theme, dark variant OK)
- [x] Meta API returns modes + templates; in-process API test passes
- [x] Playwright smoke: page loads, no console errors
- [x] Legacy Gradio render no longer serves the route (its code remains until ticket 08)
- [x] ruff/mypy/pytest + workspace lint/build green
