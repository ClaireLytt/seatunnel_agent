# 10: i18n full parity (~247 keys) + dark-mode pass

**What to build:** Every visible string on the page is localized zh/en, ported verbatim from the legacy dictionary into i18next, initialized from the language cookie; the server keeps only backend-rendered message keys. A full visual pass confirms the dark variant on every section, with screenshots.

**Blocked by:** 04, 06, 07, 08, 09

**Status:** done

- [x] Verbatim-parity test against the legacy dictionary (inline literals per established pattern)
- [x] No hardcoded display strings in the workspace; language switch covers everything
- [x] Dark screenshots of all sections saved under the reports shots directory
- [x] Project verification commands green
