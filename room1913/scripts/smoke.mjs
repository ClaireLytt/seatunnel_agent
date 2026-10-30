// Smoke test for Room 1913 — pages respond and the deterministic garden APIs
// behave. Requires a running server (npm run dev) on BASE.
//
//   npm run smoke            # against http://localhost:3000
//   SMOKE_BASE=... npm run smoke
//
// Test records are written under a "smoke-" clientId and removed from
// data/goodnews.json / data/bottles.json afterwards.

import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const BASE = process.env.SMOKE_BASE ?? "http://localhost:3000";
const CLIENT = `smoke-${Date.now()}`;
let failures = 0;

function check(name, cond, detail = "") {
  if (cond) {
    console.log(`  ok   ${name}`);
  } else {
    failures++;
    console.error(`  FAIL ${name}${detail ? ` — ${detail}` : ""}`);
  }
}

async function page(p, marker) {
  const res = await fetch(BASE + p);
  const body = await res.text();
  check(`GET ${p}`, res.status === 200 && body.includes(marker), `status ${res.status}`);
}

async function api(method, p, body) {
  const res = await fetch(BASE + p, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let json = null;
  try { json = await res.json(); } catch {}
  return { status: res.status, json };
}

async function cleanup() {
  for (const file of ["data/goodnews.json", "data/bottles.json", "data/capsules.json", "data/presence.json"]) {
    try {
      const fp = path.resolve(file);
      const list = JSON.parse(await readFile(fp, "utf-8"));
      const kept = list.filter(x => !String(x.clientId ?? "").startsWith("smoke-"));
      if (kept.length !== list.length) {
        await writeFile(fp, JSON.stringify(kept, null, 2), "utf-8");
      }
    } catch {}
  }
}

try {
  await fetch(BASE, { signal: AbortSignal.timeout(4000) });
} catch {
  console.error(`No server at ${BASE} — start one first (npm run dev).`);
  process.exit(2);
}

console.log(`smoke against ${BASE}`);

// pages render with their landmarks
await page("/home", "SESSION");
await page("/room", "mirror on the wall");
await page("/archive", "ARCHIVE");
await page("/map", "SUBCONSCIOUS");
await page("/garden", "GARDEN");

// good news: validation, classify, exchange, one-per-day
{
  const bad = await api("POST", "/api/goodnews", {});
  check("goodnews rejects empty", bad.status === 400);

  const first = await api("POST", "/api/goodnews", {
    text: "smoke: finally fixed the leaking tap",
    clientId: CLIENT,
  });
  check("goodnews accepts a note", first.status === 200 && !!first.json?.mine?.pillar);
  check("goodnews returns an exchange", !!first.json?.match?.text);

  const again = await api("POST", "/api/goodnews", {
    text: "smoke: second note same day",
    clientId: CLIENT,
  });
  check("goodnews is one per day", again.json?.already === true);

  const got = await api("GET", `/api/goodnews?clientId=${CLIENT}`);
  check("goodnews GET returns mine", got.json?.mine?.clientId === CLIENT);
  check("goodnews GET returns history", Array.isArray(got.json?.history) && got.json.history.length === 1);

  const ownLamp = await api("POST", "/api/goodnews/lamp", {
    id: got.json.mine.id,
    clientId: CLIENT,
  });
  check("lamp refuses your own note", ownLamp.status === 400);

  const otherLamp = await api("POST", "/api/goodnews/lamp", {
    id: got.json.mine.id,
    clientId: `${CLIENT}-other`,
  });
  check("lamp lights another's note", otherLamp.json?.lit === true && otherLamp.json?.litCount === 1);

  const dupLamp = await api("POST", "/api/goodnews/lamp", {
    id: got.json.mine.id,
    clientId: `${CLIENT}-other`,
  });
  check("lamp dedupes per visitor", dupLamp.json?.litCount === 1);
}

// reply: validation, no self-reply, one per visitor
{
  const got = await api("GET", `/api/goodnews?clientId=${CLIENT}`);
  const noteId = got.json.mine.id;

  const empty = await api("POST", "/api/goodnews/reply", { id: noteId, clientId: `${CLIENT}-other` });
  check("reply rejects empty text", empty.status === 400);

  const self = await api("POST", "/api/goodnews/reply", { id: noteId, clientId: CLIENT, text: "hi" });
  check("reply refuses your own note", self.status === 400);

  const first = await api("POST", "/api/goodnews/reply", { id: noteId, clientId: `${CLIENT}-other`, text: "smoke: nice one" });
  check("reply lands on another's note", first.json?.replied === true && !first.json?.already);

  const dup = await api("POST", "/api/goodnews/reply", { id: noteId, clientId: `${CLIENT}-other`, text: "smoke: again" });
  check("reply is one per visitor", dup.json?.already === true);

  const after = await api("GET", `/api/goodnews?clientId=${CLIENT}`);
  check("reply visible to the author", after.json?.mine?.replies?.length === 1);
}

// bottle post: validation and exchange
{
  const bad = await api("POST", "/api/bottle", { clientId: CLIENT });
  check("bottle rejects empty", bad.status === 400);

  const cast = await api("POST", "/api/bottle", {
    text: "smoke: a line for a stranger",
    clientId: CLIENT,
  });
  check("bottle washes one ashore", cast.json?.cast === true && !!cast.json?.received?.text);
}

// time capsule: validation, sealing, sealed view
{
  const bad = await api("POST", "/api/capsule", { text: "x", clientId: CLIENT, days: 7 });
  check("capsule rejects odd horizons", bad.status === 400);

  const sealed = await api("POST", "/api/capsule", {
    text: "smoke: dear future self",
    clientId: CLIENT,
    days: 90,
  });
  check("capsule seals a letter", sealed.json?.sealed?.sealed === true);
  check("capsule hides sealed text", sealed.json?.sealed?.text === undefined);

  const got = await api("GET", `/api/capsule?clientId=${CLIENT}`);
  check("capsule GET lists own capsules", got.json?.capsules?.length === 1 && got.json.capsules[0].sealed === true);

  const notMine = await api("GET", `/api/capsule?clientId=${CLIENT}-other`);
  check("capsule GET hides others' capsules", notMine.json?.capsules?.length === 0);
}

// presence: validation and window counting
{
  const bad = await api("POST", "/api/presence", {});
  check("presence rejects missing clientId", bad.status === 400);

  await api("POST", "/api/presence", { clientId: `${CLIENT}-a` });
  const second = await api("POST", "/api/presence", { clientId: `${CLIENT}-b` });
  check("presence counts the other visitor", second.json?.others >= 1);

  const repeat = await api("POST", "/api/presence", { clientId: `${CLIENT}-b` });
  check("presence dedupes repeated beats", repeat.json?.others === second.json?.others);
}

await cleanup();
console.log(failures ? `\n${failures} failure(s)` : "\nall green");
process.exit(failures ? 1 : 0);
