# Room 1913

A minimal, atmospheric web prototype: a midnight European study where you can speak with Jung, Freud, Adler, Lacan — and, from a sunnier century, Martin Seligman.

## Local

```bash
npm install
cp .env.local.example .env.local   # then paste your real ANTHROPIC_API_KEY
npm run dev
```

Open http://localhost:3000.

## Deploy to Vercel

1. `npm i -g vercel` (or use the dashboard).
2. Push this folder to a Git repo, then import it at vercel.com/new.
3. In the Vercel project's **Environment Variables**, add:
   - `ANTHROPIC_API_KEY` = your key from console.anthropic.com
   - `KV_REST_API_URL` and `KV_REST_API_TOKEN` = a Vercel KV / Upstash
     Redis REST endpoint, so the garden's shared collections (good news,
     bottles, capsules) persist — on serverless hosts the filesystem is
     ephemeral, and without these the garden falls back to per-instance
     files that vanish between deploys
4. Deploy.

The API key is only ever read on the server in `app/api/chat/route.ts` — it is never sent to the browser.

## The Garden (/garden)

A fifth resident, Martin Seligman, brings positive psychology into the room.
Everything below is deterministic — no API key needed.

- **Daily good news** — share one small good thing a day; it is classified
  into a PERMA pillar and exchanged with another visitor's note of the same
  pillar. Light a lamp back for the note you receive.
- **Flowerbed & calendar** — every shared note grows a flower in its pillar
  color; a month grid blooms on the days you shared.
- **Three good things** — Seligman's evening exercise; an oil lamp burns
  brighter with your streak.
- **Five questions** — one question per PERMA pillar, revealing a five-bar
  profile.
- **Learned optimism** — nine setback cards scored across permanence,
  pervasiveness and personalization.
- **Signature strengths** — twelve either/or cards over twelve VIA character
  strengths, revealing your top three.
- **Breathing window** — a three-minute 4-7-8 exercise by lamplight.
- **Bottle post** — cast a line into the rain for a stranger; another
  visitor's bottle washes ashore.

The garden reaches the rest of the room: good news kept in the last seven
days softens the rain and warms the window, the subconscious map gains a warm
PERMA radar, and once tonight's three good things are written the wall mirror
answers in Seligman's register.

Shared notes live in `data/*.json` (gitignored); everything personal stays in
the browser's localStorage.
