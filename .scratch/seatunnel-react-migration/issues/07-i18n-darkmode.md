# 07: i18n full parity + dark-mode pass

**What to build:** Every visible string on the page is localized in zh and en, ported verbatim from the page's Python i18n dict into i18next, initialized from the language cookie. A full visual pass confirms the dark variant renders correctly on every section.

**Blocked by:** 03, 04, 05, 06

**Status:** ready-for-agent

- [ ] zh/en switch via language cookie covers all sidebar + chat + control strings
- [ ] No hardcoded display strings remain in the workspace
- [ ] Dark variant verified on all sections (screenshots)
- [ ] ruff/mypy/pytest + workspace lint/build green
