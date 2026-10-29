// Suitcase — carry the room's per-browser records to another browser.
// Export bundles every room1913.* localStorage key; import merges, never
// deleting what is already here.

const KEYS = [
  "room1913.archive.v1",
  "room1913.memory.v1",
  "room1913.goodthings.v1",
  "room1913.garden.client.v1",
  "room1913.garden.answers.v1",
  "room1913.garden.optimism.v1",
  "room1913.garden.strengths.v1",
  "room1913.garden.lampseen.v1",
  "room1913.flow.v1",
  "room1913.salon.v1",
  "room1913.garden.results.v1",
  "room1913.dreams.v1",
];

export interface Suitcase {
  room: "1913";
  version: 1;
  exportedAt: number;
  data: Record<string, string>;
}

export function packSuitcase(): Suitcase {
  const data: Record<string, string> = {};
  for (const k of KEYS) {
    try {
      const v = localStorage.getItem(k);
      if (v !== null) data[k] = v;
    } catch {}
  }
  return { room: "1913", version: 1, exportedAt: Date.now(), data };
}

function mergeListByKey(existing: string, imported: string, idOf: (x: any) => string): string {
  const a = JSON.parse(existing);
  const b = JSON.parse(imported);
  if (!Array.isArray(a) || !Array.isArray(b)) return existing;
  const seen = new Set(a.map(idOf));
  for (const item of b) {
    if (!seen.has(idOf(item))) { a.push(item); seen.add(idOf(item)); }
  }
  return JSON.stringify(a);
}

// Returns a human summary line, or throws on an unreadable file.
export function unpackSuitcase(raw: string): string {
  const s = JSON.parse(raw) as Suitcase;
  if (s?.room !== "1913" || !s.data || typeof s.data !== "object") {
    throw new Error("not a Room 1913 suitcase");
  }
  let applied = 0;
  for (const [k, v] of Object.entries(s.data)) {
    if (!KEYS.includes(k) || typeof v !== "string") continue;
    try {
      const cur = localStorage.getItem(k);
      if (cur === null || cur === "" || cur === "[]" || cur === "{}") {
        localStorage.setItem(k, v);
        applied++;
      } else if (k === "room1913.goodthings.v1") {
        localStorage.setItem(k, mergeListByKey(cur, v, (e: any) => e.day));
        applied++;
      } else if (k === "room1913.archive.v1") {
        localStorage.setItem(k, mergeListByKey(cur, v, (e: any) => e.id));
        applied++;
      }
      // anything else that already holds data stays as it is
    } catch {}
  }
  return `${applied} 项记录已带入这个房间`;
}

export function suitcaseFilename(): string {
  const d = new Date();
  const ymd = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return `room1913-suitcase-${ymd}.json`;
}
