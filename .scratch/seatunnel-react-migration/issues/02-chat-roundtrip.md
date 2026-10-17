# 02: Chat round-trip — message in, SSE stream out, Stop

**What to build:** A user types a message, presses Send, and the agent's response streams into the chat area event-by-event (SSE via the shared SSE helper); a Stop control interrupts a running generation. The chat endpoint drives the existing seatunnel agent tool-execution path unchanged.

**Blocked by:** 01 — Walking skeleton

**Status:** done

- [x] Sending a message renders a streaming assistant reply in the chat area
- [x] Stop interrupts the stream and leaves the partial reply visible
- [x] In-process API test asserts the SSE event stream shape
- [x] ruff/mypy/pytest + workspace lint/build green
