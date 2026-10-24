# Spec: Fix findings from the 2026-10-24 full-UI browser sweep

Labels: `ready-for-agent`
(Tracker/triage vocabulary was not provided to this session — run `/setup-matt-pocock-skills` to configure it. Spec kept as a local file per policy; no GitHub issue created.)

## Problem Statement

A full browser sweep of all 26 pages on http://127.0.0.1:7860/ found that while every page renders and degrades gracefully without an LLM/Hive, six concrete defects undermine trust in the platform:

1. The SeaTunnel Pipeline Builder **Demo** flow reports success on a config that was never written: `write_config` is refused (temp path outside the working directory), yet `validate_config` then reports "Config is valid" for the missing file and the final summary claims "Config generated and validated! Saved to …".
2. Chinese strings leak into the English UI: Test Data Generator notes ("推断类型: …"), the Data Lineage governance report title ("血缘治理体检报告"), and the Orchestrator's no-LLM fallback agent descriptions.
3. The Text2SQL History (query log) shows many rows with an empty Question column, making the log useless for auditing those calls.
4. The MCP Toolbox page lists several tools (`skew_runtime_eventlog`, `skew_runtime_history`, `skew_split_key`, `skew_split_key_file`, …) with an empty "What it does" cell.
5. Opening a UI Testing Agent report logs a console error — the report iframe is sandboxed without `allow-scripts`, so any script in the HTML report is blocked.
6. Secret Scan misses common password variable names: `db_password = "SuperSecret123!"` is not flagged because the `password_assign` rule's `\b` boundary does not match after `db_` (underscore is a word character).

## Solution

Fix each defect at its root with a deterministic regression test, so a re-run of the same browser sweep (or the uitest smoke suite) shows: a demo flow that is honest about failure, a fully language-consistent English UI, a query log whose every row carries its question, a complete MCP tool table, a clean console when viewing uitest reports, and a secret scanner that catches `*_password` style assignments.

## User Stories

1. As a pipeline builder user, I want the Demo flow to write its config to a permitted path, so that the demo actually produces a usable file.
2. As a pipeline builder user, I want `validate_config` to fail clearly when the config file does not exist, so that I never see "valid" for a file that was never written.
3. As a pipeline builder user, I want the demo summary to reflect what actually happened (including tool failures), so that I can trust agent run transcripts.
4. As an English-locale user of the Test Data Generator, I want the inferred-types note rendered in English, so that the report is readable without knowing Chinese.
5. As an English-locale user of Data Lineage, I want the governance health report title and sections in English, so that the report matches the rest of the page.
6. As an English-locale user of the Orchestrator, I want the no-LLM fallback agent suggestions described in English, so that routing hints are understandable.
7. As a Chinese-locale user, I want those same strings to remain Chinese when the UI language is 中文, so that the fix does not regress the Chinese experience.
8. As a Text2SQL user auditing the query log, I want every history row to show the originating question (or a well-defined placeholder such as the calling channel), so that I can tell what produced each query.
9. As a Text2SQL user, I want MCP- and subscription-originated queries labeled consistently in the log, so that non-interactive traffic is distinguishable from chat questions.
10. As an MCP Toolbox visitor, I want every listed tool to carry a one-line description, so that I can pick the right tool without reading source code.
11. As a maintainer, I want a test that fails whenever a registered MCP tool lacks a description, so that new tools cannot ship undocumented.
12. As a UI Testing Agent user, I want report viewing to produce zero console errors, so that the page meets the project's clean-console standard.
13. As a UI Testing Agent user, I want interactive parts of the HTML report (if any) to work inside the viewer, so that the embedded report is not silently degraded.
14. As a security engineer running Secret Scan, I want `db_password`, `mysql_password`, `root_pwd` and similar prefixed assignments flagged, so that realistic leaks are not missed.
15. As a security engineer, I want genuine placeholders (e.g. `password = "changeme"` style examples) to keep being filtered, so that the broadened rule does not flood results with noise.
16. As a maintainer, I want regression tests for each fix at existing test seams, so that the defects cannot silently return.
17. As a release reviewer, I want the uitest smoke suite to stay green after these fixes, so that the sweep's "all pages render" baseline is preserved.

## Implementation Decisions

- **Demo flow honesty (seatunnel agent)** — three coordinated changes in the seatunnel agent's tool layer and demo script:
  - The demo writes its config under the working directory (or another path the dir-guard whitelists), not the OS temp dir.
  - `validate_config` checks file existence first and returns an error for a missing file instead of "Config is valid".
  - The demo's final summary is derived from tool outcomes: if `write_config` failed, the summary must say so and must not claim the file was saved. Reuse the existing single dir-guard (`common/api_guard`) rather than adding a second path check.
- **i18n consistency** — the three offending render sites take the page's language parameter (the pattern already used elsewhere: EN/中文 string pairs selected by a `lang` key). Add English counterparts for the testgen inferred-types note, the lineage governance report headings, and pass the UI language through the orchestrator's no-LLM fallback so agent descriptions render in the active language (agent registry descriptions already exist in Chinese; add English descriptions alongside, keyed by language).
- **Text2SQL query log** — every writer of the query log must populate the question field; non-chat channels (MCP tool calls, subscriptions) write a bracketed channel tag plus whatever question text they have (the existing `[mcp] …` / `[subscription] …` convention), never an empty string. The history renderer shows a literal em-dash for legacy empty rows rather than a blank cell.
- **MCP Toolbox descriptions** — the toolbox page builds its table from the tool registry; the skew runtime/split-key tools get one-line descriptions at their registration site. Add a guard that the table source derives descriptions from the same metadata the MCP server exposes (single source, no hand-maintained copy in the UI module).
- **uitest report iframe** — the report viewer's iframe sandbox gains `allow-scripts`. Keep `allow-same-origin` only if the report genuinely needs it; prefer `sandbox="allow-scripts"` alone to avoid the sandbox-escape combination of both flags on same-origin content. Decide based on what the generated report HTML actually uses.
- **Secret Scan password rule** — broaden the `password_assign` pattern to match identifiers *ending* in `password|passwd|pwd` (e.g. `(?i)\b[\w.-]*(?:password|passwd|pwd)\s*[:=]`), keeping the existing value-length and placeholder filters intact.
- No schema changes, no new API endpoints, no new modules; all fixes land inside existing modules behind existing interfaces.
- UI rule reminder: no blue-purple palette anywhere a style is touched (only the iframe attribute changes in frontend; no visual changes expected).

## Testing Decisions

- Good tests here assert **external behavior**: tool return strings, rendered report text, log-row contents, registry metadata completeness, and browser console cleanliness — never internal call sequences.
- Seams (all existing; no new seams proposed):
  1. **Agent tool functions** (seatunnel `validate_config` / demo script) — direct pytest over the tools module, the same seam existing seatunnel tool tests use.
  2. **Render functions** (testgen generator notes, lineage render, orchestrator fallback) — pytest asserting EN and 中文 outputs per `lang`.
  3. **Query-log writer** (text2sql qlog) — pytest that each write path produces a non-empty question field.
  4. **Registry/metadata** (MCP toolbox) — pytest iterating registered tools and asserting non-empty descriptions (same style as `tests/test_registry.py` manifest checks).
  5. **Secret Scan rules** — pytest over `scan` with `db_password = "..."` fixtures (positive) and placeholder fixtures (negative).
  6. **Browser seam** — the existing uitest YAML suite: a case that opens a past uitest report and asserts no console errors (the suite already captures console output; follow the existing case format in `config/uitest_cases/`).
- Prior art: existing unit tests per agent under `tests/`, the derived-assertion pattern in `tests/test_ui_testing.py`, and registry completeness tests in `tests/test_registry.py`.

## Acceptance Criteria

Every criterion is verified against the real artifact, not a proxy.

1. `ruff check src tests scripts` → ends `All checks passed!` (all stories).
2. `mypy` → ends `Success: no issues found` (all stories).
3. `pytest` → ends `N passed` with N ≥ current baseline, including the new tests named below (stories 1–11, 14–16):
   - seatunnel: validate-missing-file test fails before fix, passes after (stories 1–3);
   - testgen/lineage/orchestrator i18n tests assert both languages (stories 4–7);
   - qlog test asserts non-empty question on every write path (stories 8–9);
   - registry test asserts every MCP tool has a description (stories 10–11);
   - secretscan tests: `db_password = "SuperSecret123!"` flagged, placeholder not flagged (stories 14–15).
4. `python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm` → report verdict `PASS`, report path attached as evidence (story 17).
5. Real-browser verification (screenshots required as evidence, per repo rule §5):
   - seatunnel page Demo click: transcript shows either a successful write to a permitted path **or** a summary that admits failure; no "valid"/"saved" claim for a missing file (stories 1–3);
   - English pages show no Chinese in the three fixed locations; 中文 UI still shows Chinese (stories 4–7);
   - uitest report View click with DevTools console open: zero errors (stories 12–13);
   - MCP Toolbox table has no empty "What it does" cells (story 10).
6. `npm run lint --workspace uitest` and `npm run build --workspace uitest` succeed (stories 12–13).
7. `python scripts/check_workflow.py` → PASS output attached to the batch report (process requirement).
8. Batch report written to `docs/reports/<YYYYMMDD>-ui-sweep-fixes.md` per TEMPLATE, including before/after evidence for each finding (process requirement).

## Out of Scope

- Configuring an LLM API key or Hive connection (environment, not code).
- Any redesign of the demo flow beyond making it honest and path-correct.
- Full i18n audit of the whole platform — only the three locations found in the sweep.
- Backfilling questions into existing (historical) query-log rows.
- Network-dependent Secret Scan features (CVE lookups etc.).
- New MCP tools or changes to tool behavior — descriptions only.

## Further Notes

- Findings originate from a live Chrome DevTools MCP sweep on 2026-10-24 against a running `seatunnel-agent ui` on port 7860; all page-level observations are recorded in the conversation and screenshots in the session's tool-results directory.
- The earlier "Migrate button ignores pasted text" observation was a test-harness artifact (MCP `fill` not firing Gradio events), not an app bug — keyboard input works. Matches the known Gradio testing gotcha; no fix needed.
- Per CLAUDE.md §7 批次工作流: this spec is the problem list; implementation waits for explicit batch approval ("批次 N"), one batch per logical group suggested: 批次1 = demo honesty (finding 1), 批次2 = i18n (2), 批次3 = logs/descriptions (3–4), 批次4 = frontend iframe (5), 批次5 = secretscan rule (6).
