# 11: Retire the legacy Gradio page

**What to build:** One implementation remains. Delete the legacy UI modules (anything the REST layer still needs was moved in ticket 01), prune hub CSS classes that grep proves unreferenced after this page leaves, update UI-test engine references and YAML cases targeting the page, fix hardcoded test enumerations, land the Playwright page test as the page's regression coverage, capture before screenshots from the pre-migration commit, and write the batch report.

**Blocked by:** 10 — i18n + dark mode

**Status:** ready-for-agent

- [ ] Legacy UI modules deleted; no dangling imports, CSS, i18n keys, case refs (grep evidence)
- [ ] uitest smoke suite green; Playwright page test passes
- [ ] Before/after screenshots under the reports shots directory
- [ ] Batch report per template; workflow check script passes
- [ ] Project verification commands green
