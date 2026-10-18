# 04: Compound actions with progress — compare-all / batch count / profile / batch full

**What to build:** The heavy actions run with live progress feedback (SSE via the shared helper, or polling — implementer picks the simpler equivalent of today's feedback) and a double-trigger guard, rendering their result cards on completion.

**Blocked by:** 03 — Core actions

**Status:** done

- [x] All four compound actions complete and render cards; progress visible during the run
- [x] Double-click cannot start a second concurrent run
- [x] In-process API test covers compare-all contract incl. progress signal
- [x] Project verification commands green
