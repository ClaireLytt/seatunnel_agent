import { NextResponse } from "next/server";
import { readCollection, writeCollection } from "@/app/lib/store";

export const runtime = "nodejs";

// Time capsule — a letter to your future self. Sealed until its date;
// only ever shown to the visitor who wrote it.

interface Capsule {
  id: string;
  clientId: string;
  text: string;
  createdAt: number;
  openAt: number;
}

const ALLOWED_DAYS = [90, 180, 365];

const loadCapsules = () => readCollection<Capsule>("capsules");

function view(c: Capsule, now: number) {
  return c.openAt <= now
    ? { id: c.id, createdAt: c.createdAt, openAt: c.openAt, sealed: false, text: c.text }
    : { id: c.id, createdAt: c.createdAt, openAt: c.openAt, sealed: true };
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const clientId = (url.searchParams.get("clientId") ?? "").slice(0, 64);
  if (!clientId) return NextResponse.json({ capsules: [] });
  const now = Date.now();
  const list = await loadCapsules();
  const capsules = list
    .filter(c => c.clientId === clientId)
    .sort((a, b) => a.openAt - b.openAt)
    .map(c => view(c, now));
  return NextResponse.json({ capsules });
}

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as { text?: string; clientId?: string; days?: number };
    const text = String(body.text ?? "").trim().slice(0, 600);
    const clientId = String(body.clientId ?? "").trim().slice(0, 64);
    const days = Number(body.days);
    if (!text || !clientId) {
      return NextResponse.json({ error: "empty letter" }, { status: 400 });
    }
    if (!ALLOWED_DAYS.includes(days)) {
      return NextResponse.json({ error: "pick a real horizon" }, { status: 400 });
    }
    const now = Date.now();
    const capsule: Capsule = {
      id: `cp-${now}-${Math.random().toString(36).slice(2, 8)}`,
      clientId,
      text,
      createdAt: now,
      openAt: now + days * 24 * 60 * 60 * 1000,
    };
    const list = await loadCapsules();
    list.push(capsule);
    await writeCollection("capsules", list);
    return NextResponse.json({ sealed: view(capsule, now) });
  } catch (err) {
    console.error("capsule error", err);
    return NextResponse.json({ error: "the wax would not set" }, { status: 500 });
  }
}
