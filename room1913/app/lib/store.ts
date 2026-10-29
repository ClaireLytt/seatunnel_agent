// Shared-data store for the garden's collections (goodnews, bottles,
// capsules). Two drivers:
//
//   file — data/<name>.json, the default; right for local dev and
//          self-hosting, where the filesystem persists
//   kv   — any Upstash-compatible Redis REST endpoint (Vercel KV,
//          Upstash), selected when KV_REST_API_URL and
//          KV_REST_API_TOKEN are set; required on serverless hosts,
//          whose filesystem is ephemeral
//
// Each collection is one JSON array under one key — plenty for a
// prototype's write volume, and trivially portable between drivers.

import { promises as fs } from "fs";
import path from "path";

const DATA_DIR = path.join(process.cwd(), "data");

const KV_URL = process.env.KV_REST_API_URL ?? "";
const KV_TOKEN = process.env.KV_REST_API_TOKEN ?? "";
const useKv = Boolean(KV_URL && KV_TOKEN);

function kvKey(name: string): string {
  return `room1913:${name}`;
}

async function kvFetch(cmd: string[]): Promise<any> {
  const res = await fetch(`${KV_URL}/${cmd.map(encodeURIComponent).join("/")}`, {
    headers: { Authorization: `Bearer ${KV_TOKEN}` },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`kv ${cmd[0]} failed: ${res.status}`);
  return (await res.json())?.result;
}

export async function readCollection<T>(name: string): Promise<T[]> {
  try {
    if (useKv) {
      const raw = await kvFetch(["get", kvKey(name)]);
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    }
    const raw = await fs.readFile(path.join(DATA_DIR, `${name}.json`), "utf-8");
    const list = JSON.parse(raw);
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export async function writeCollection<T>(name: string, list: T[]): Promise<void> {
  if (useKv) {
    await kvFetch(["set", kvKey(name), JSON.stringify(list)]);
    return;
  }
  await fs.mkdir(DATA_DIR, { recursive: true });
  await fs.writeFile(
    path.join(DATA_DIR, `${name}.json`),
    JSON.stringify(list, null, 2),
    "utf-8"
  );
}
