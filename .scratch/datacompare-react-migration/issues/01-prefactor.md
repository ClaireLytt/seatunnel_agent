# 01: Prefactor — pure card renderers + per-session connection registry

**What to build:** The Gradio page behaves exactly as before, but its card rendering lives in a Gradio-free module of pure functions, and connection/table/report state lives in a server-side per-session connection registry instead of the module-global holder. This makes the React migration's REST layer a thin consumer. All existing tests stay green.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Card renderers importable without Gradio; Gradio page consumes them
- [ ] Connection state keyed per session (registry), Gradio page behavior unchanged
- [ ] Full test suite green; no behavior change observable in the browser
