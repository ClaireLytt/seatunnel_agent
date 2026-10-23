# 01: Expand: grow ToolLoopAgent's interface (events, stop, hint, truncation)

**What to build:** The shared bounded tool-use loop gains the four optional seams the hand-rolled loops prove necessary, with defaults preserving today's behavior exactly: a typed event callback (tool step, text delta, usage), a stop signal checked between turns and tool calls (a stopped run returns a result marked stopped), a per-turn system-hint hook, and a message-truncation policy applied before each client call. Nothing user-visible changes; the four existing adopters (code_fix, web_task, issue_triage, doctor) are untouched.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] All four seams optional; omitting them reproduces current behavior bit-for-bit (existing adopters' tests green unchanged)
- [ ] Loop-level scripted-client tests cover: stop mid-run, text-delta emission, usage events, per-turn hint, truncation policy, dangling tool_use repair, forced summary
- [ ] Shared Step/LoopResult remain the single loop-telemetry schema (extended only if an event type demands it)
- [ ] ruff/mypy + full pytest green

