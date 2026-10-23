# 06: Migrate seatunnel chat onto the shared loop (stop, text-delta, truncation)

**What to build:** SeaTunnel chat behaves identically — progressive token rendering, prompt Stop-button halt, long-session truncation — with the hand-rolled loop deleted; stop/delta/truncation ride the shared loop's new seams and the per-turn context hint rides the hint hook.

**Blocked by:** 01, 02 (first migration must prove the seams before the primary chat surface moves).

**Status:** done (2026-10-23)

- [x] Local loop deleted; stop/delta/usage/truncation via the shared seams
- [x] Existing seatunnel API + Playwright page tests green unchanged; stop/stream verified in a real browser (uitest smoke at batch close)
- [x] One offline loop test added (scripted client)
- [x] ruff/mypy + targeted tests green

