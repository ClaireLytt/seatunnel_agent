# 01: Single-source the bad_dir guard as require_dir in common api_guard

**What to build:** A user submitting a directory to any of the seven directory-taking agent endpoints (config_lint, config_migrate, dag_check, data_lineage, pii_scan, sql_fmt, sql_transpile) gets byte-identical responses to today — 403 for a non-allowlisted path (no existence probing), structured 400 `{code: "bad_dir", path}` for a missing dir — but the guard is one shared `require_dir(path, env_var)` in the common api_guard module beside `check_path_allowed`, hoisted from data_lineage's local `_require_dir` (the prototype). All seven routers call it; inline copies and the local helper are deleted. Any variant with extra detail keys stays inline and is noted.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] `require_dir` exists once in api_guard; whitelist-before-existence ordering encoded there
- [ ] Seven routers call it; zero inline copies remain (grep for the bad_dir raise outside api_guard)
- [ ] Endpoint signatures, response models, and error payloads unchanged; the seven agents' API tests green unchanged
- [ ] ruff/mypy pass
