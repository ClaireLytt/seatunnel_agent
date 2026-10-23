# Spec: One deep ToolLoopAgent (converge the five hand-rolled ReAct loops)

Triage: `ready-for-agent`

## Problem Statement

As a maintainer of the agent platform, the bounded tool-use loop — "LLM with tools acts, observes, iterates until a plain-text answer or max_steps, then one forced summary turn" — exists six times. The shared `ToolLoopAgent` (agent_core) serves four agents (code_fix, web_task, issue_triage, doctor), while seatunnel, text2sql, sql_review, data_lineage and the orchestrator (the drifted original) each hand-roll their own `_agent_loop`. The copies have diverged: stop-event handling, text-delta streaming, an `on_event` protocol, usage events and message truncation exist in some copies and not others; the dangling-tool_use repair exists only in the shared loop. A loop bug must be fixed in up to six places, and the injectable scripted-client test seam — the reason the shared loop tests offline — is unavailable to the five hold-outs, which are the least-tested code in the repo.

## Solution

Deepen the one loop module instead of maintaining six. `ToolLoopAgent`'s interface grows by exactly the seams the hold-outs prove necessary — an optional event callback (tool steps, text deltas, usage), a stop signal, a per-turn system hint, and a message-truncation policy — and the five agents shrink to what is genuinely theirs: tool sets, prompts, few-shot/context augmentation, and event-to-SSE plumbing. Behavior of every page and CLI stays the same; loop semantics gain one home.

## User Stories

1. As a platform maintainer, I want the tool-use loop implemented once, so that a loop bug fix (e.g. dangling tool_use repair) lands everywhere at once.
2. As a chat user pressing Stop, I want generation to halt promptly, so that I'm not billed for a run I abandoned — with stop handling implemented in the loop, not re-invented per agent.
3. As a chat user, I want streaming text deltas as the model writes, so that long answers render progressively — via the loop's event seam.
4. As an agent developer, I want to build a new agent by supplying tools + prompts to the shared loop, so that I never write loop plumbing.
5. As an agent developer, I want an `on_event` callback covering step, text-delta and usage events, so that SSE endpoints can forward loop progress without reaching into the loop.
6. As a maintainer of long chat sessions, I want message truncation as a loop policy, so that context-window management is uniform rather than seatunnel-only.
7. As a test author, I want every agent's loop driven by the injectable scripted client, so that the five currently hard-to-test agents gain offline loop tests.
8. As a maintainer, I want the orchestrator to drop its duplicate Step/Result dataclasses in favor of the shared ones, so that loop telemetry has one schema.
9. As a user of any migrated page (seatunnel chat, text2sql, sql_review, lineage, orchestrator), I want identical visible behavior — same answers, same streamed events, same stop semantics, so that the refactor is invisible.
10. As a maintainer, I want each migration to land separately with its page/API tests green, so that a regression is bisectable to one agent.
11. As a reviewer, I want the loop's new seams to be optional with defaults preserving current shared-loop behavior, so that the four existing adopters are untouched until they opt in.
12. As a maintainer, I want per-turn system hints (seatunnel's context injection) supported through the interface, so that the last hold-out capability has a home.
13. As a cost watcher, I want usage events surfaced through the same event seam, so that per-turn token accounting doesn't require a custom loop.
14. As a maintainer, I want any agent whose loop semantics genuinely diverge left alone with the divergence documented, so that convergence never forces behavior change.

## Implementation Decisions

- The one seam is the agent_core loop module's interface. It grows (all optional, defaulting to today's behavior):
  - an event callback invoked for tool steps (exists today as `on_step`), text deltas, and usage — one callback, typed events, generalizing the hold-outs' `EventCallback` protocols;
  - a stop signal (threading.Event or equivalent) checked between turns and between tool calls; a stopped run returns a LoopResult marked stopped;
  - a per-turn system-hint hook (callable returning extra system text), covering seatunnel's context injection;
  - a truncation policy applied to messages before each client call, generalizing seatunnel's `truncate_messages` use.
- The shared Step/LoopResult dataclasses are the single loop-telemetry schema; the orchestrator's duplicates are deleted in its migration.
- Migration order: orchestrator first (the drifted original; richest telemetry tests), then sql_review and data_lineage (plain loops), then text2sql and seatunnel (event/stop/truncation consumers). Each agent keeps its own tools, prompts, few-shot augmentation and SSE wiring; only the loop body is replaced.
- The loop stays synchronous; SSE endpoints keep their existing queue/thread bridges (SSE transport convergence is candidate 5, a separate effort).
- Scripted-client fakes in tests standardize on the shared conftest `llm_text`/`llm_tool` builders (already converged).
- If a hold-out's loop reveals a semantic the interface can't host cleanly (e.g. text2sql's result-event protocol), prefer hosting it in the agent via the event callback rather than widening the loop interface; document any copy deliberately left.

## Testing Decisions

- The loop's interface is the test surface: new loop-level tests (scripted client) cover stop-mid-run, text-delta emission order, truncation policy, per-turn hint, dangling tool_use repair, forced summary — once, in agent_core tests (prior art: existing loop/orchestrator tests with ScriptedClient).
- Per migrated agent, the proof is existing external-behavior tests staying green unchanged: FastAPI TestClient suites and Playwright page tests (chat pages' stream/stop flows).
- Each migration adds one offline loop test for that agent (tools wired, scripted client) — the leverage the migration buys.
- Full pytest + uitest smoke at batch close per repo rules.

## Out of Scope

- SSE transport convergence (candidate 5) — the chat APIs keep their queue/thread bridges.
- comparator.py deepening, Vite scaffold presets, api_factory adoption (candidates 2–4).
- Any prompt, tool, or model-behavior change; any new user-facing feature.
- Async-ifying the loop.

## Further Notes

- Seam check (flagged for confirmation): one seam — the shared loop's interface. No new modules; the five agents' loop bodies are deleted, not wrapped (replace, don't layer).
- Risk note: seatunnel/text2sql are the live chat surfaces; their migrations go last, behind green page tests, and stop/stream behavior is verified in the real browser (uitest) before batch close.
- Source: architecture review 2026-10-23, candidate 1 (exploration notes in memory scratch arch-review-notes.md).
