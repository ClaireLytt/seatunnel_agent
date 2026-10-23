# 03: Adopt shared fetchJson in text2sql and seatunnel api clients

**What to build:** The text2sql and seatunnel pages make their plain-JSON calls through the shared `fetchJson`, so non-2xx handling is uniform; users see the same error text as today (fetchJson's ApiError extends Error with message = detail). Hand-rolled `!r.ok → throw Error(...)` blocks are deleted. Each catch site is checked file-by-file; any call site that inspects the error beyond `message`, or any fetch with genuinely different semantics (SSE/streaming stays on the SSE helper), is left alone and noted.

**Blocked by:** None (can start immediately).

**Status:** done (2026-10-23)

- [x] All convertible plain-JSON fetches in the two workspaces go through fetchJson; non-converted calls listed with reasons
- [x] Error text rendered by the pages unchanged (page tests green)
- [x] `npm run lint`/`npm run build` for both workspaces pass
