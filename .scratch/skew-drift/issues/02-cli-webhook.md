# 02: `skew-drift` CLI, splitkey tail line, webhook

**What to build:** An operator can run `seatunnel-agent skew-drift <table>` and
read the drift verdict offline from the existing history (no database needed);
with no table it sweeps every table that has history. A `skew-splitkey` run
ends with the drift-vs-baseline line in the same report that measured the key.
`--webhook` posts the drift verdict through the existing patrol webhook so
DingTalk/WeCom/Slack channels hear about drifting keys. Output is zh/en via
the agent's existing i18n table, and the drift patrol itself lands in the
history so `skew-stats` reflects it.

**Blocked by:** 01 (Drift core).

**Status:** done

- [x] `skew-drift <table>` on a seeded temp history prints metric, baseline, current, delta; no-arg form sweeps all tables (CliRunner tests, output tail in batch report)
- [x] `skew-splitkey` report ends with the drift line (mock-executor test)
- [x] Webhook test asserts the posted payload contains the drift verdict (monkeypatched post_webhook)
- [x] zh and en both render; backend i18n key-guard test passes
- [x] Drift patrol visible via `skew-stats`; `pytest` / `ruff` / `mypy` clean; batch report + check_workflow `[PASS]` lines
