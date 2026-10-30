# Room 1913 — Roadmap

What might grow next, and what each item waits for. The current PR
(#1, the garden and its residents) is feature-complete; everything
below belongs to future PRs.

## Waiting for a valid ANTHROPIC_API_KEY

- **Gardener's weekly note** — Seligman reads your week (five questions,
  good news, three good things) and writes a short observation into the
  archive. The data is already collected; only the voice is missing.
- **The table remembers your garden** — roundtable characters may quote
  your own records back to you ("but last Wednesday you wrote that the
  rain sounded good"). Extend the chat route's memory block with a few
  recent garden lines.
- **Five questions, follow-ups** — after the PERMA profile, Seligman
  gently asks one deeper question per short answer.

## Waiting for deployment (KV configured)

The storage adapter (`app/lib/store.ts`) already switches to any
Upstash-compatible endpoint via `KV_REST_API_URL`/`KV_REST_API_TOKEN`.
Once deployed, the exchange, lamps, replies, bottles, capsules and
presence become genuinely multi-visitor. Worth revisiting then:

- **Exchange rotation** — the matcher currently returns the newest
  same-pillar note; with real traffic, rotate so every note gets its
  turn to be received.
- **Rate limits** — bottles and replies are unthrottled; fine for a
  prototype, not for a public URL.

## Next-PR candidates (deterministic, designed but not built)

- **Year album** — stitch twelve month cards into one year view.
- **English toggle** — the room is bilingual by flavor, not by switch.

## Principles to keep

- Deterministic first: every feature must work with no key and no
  database; the LLM only ever adds a voice on top.
- One quiet thing per block: no dashboards, no numbers without a reason.
- Personal data stays in the browser (suitcase for carrying); shared
  data holds no identity beyond an anonymous client id.
