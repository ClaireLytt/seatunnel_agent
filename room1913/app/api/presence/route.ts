import { NextResponse } from "next/server";
import { readCollection, writeCollection } from "@/app/lib/store";

export const runtime = "nodejs";

// Presence — anonymous heartbeats, so a visitor knows the garden is not
// empty tonight. Nothing but a client id and a timestamp, kept five minutes.

interface Beat {
  clientId: string;
  at: number;
}

const WINDOW_MS = 5 * 60 * 1000;

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as { clientId?: string };
    const clientId = String(body.clientId ?? "").trim().slice(0, 64);
    if (!clientId) {
      return NextResponse.json({ error: "missing clientId" }, { status: 400 });
    }
    const now = Date.now();
    const list = (await readCollection<Beat>("presence")).filter(
      b => now - b.at < WINDOW_MS && b.clientId !== clientId
    );
    list.push({ clientId, at: now });
    await writeCollection("presence", list);
    const others = new Set(list.map(b => b.clientId)).size - 1;
    return NextResponse.json({ others: Math.max(0, others) });
  } catch (err) {
    console.error("presence error", err);
    return NextResponse.json({ error: "the room lost count" }, { status: 500 });
  }
}
