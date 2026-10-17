# 08: Retire the legacy Gradio page

**What to build:** The repository contains a single implementation of the page. Per the react-migration checklist: delete the legacy Gradio UI module, prune its UI-chrome i18n keys and page CSS, update the UI-test engine (ready routes, labels, result selectors, agent route/label catalog), replace the page's YAML case and scattered refs with a Playwright page test (in-process uvicorn, modeled on the existing page tests), and fix hardcoded tests that enumerate pages/APIs. Produce before/after screenshots and the batch report.

**Blocked by:** 07 — i18n full parity

**Status:** ready-for-agent

- [ ] Legacy UI module deleted; no dangling imports, CSS, i18n keys, or case refs
- [ ] New Playwright page test passes; uitest smoke suite (no-LLM) green
- [ ] Before/after screenshots saved under the reports shots directory
- [ ] Batch report written per the reports template; workflow check script passes
- [ ] ruff/mypy/pytest + workspace lint/build green
