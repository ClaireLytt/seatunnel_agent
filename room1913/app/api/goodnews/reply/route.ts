import { NextResponse } from "next/server";
import { GoodNews } from "@/app/lib/perma";
import { readCollection, writeCollection } from "@/app/lib/store";

export const runtime = "nodejs";

// Reply one line to the good news you received in exchange.
export async function POST(req: Request) {
  try {
    const body = (await req.json()) as { id?: string; clientId?: string; text?: string };
    const id = String(body.id ?? "").slice(0, 64);
    const clientId = String(body.clientId ?? "").trim().slice(0, 64);
    const text = String(body.text ?? "").trim().slice(0, 100);
    if (!id || !clientId || !text) {
      return NextResponse.json({ error: "empty reply" }, { status: 400 });
    }

    const list = await readCollection<GoodNews>("goodnews");
    const note = list.find(n => n.id === id);
    // seed notes are not in the store; the gesture still lands
    if (!note) return NextResponse.json({ replied: true });
    if (note.clientId === clientId) {
      return NextResponse.json({ error: "cannot reply to your own note" }, { status: 400 });
    }

    note.replies = note.replies ?? [];
    if (note.replies.some(r => r.clientId === clientId)) {
      return NextResponse.json({ replied: true, already: true });
    }
    note.replies.push({ clientId, text, at: Date.now() });
    await writeCollection("goodnews", list);
    return NextResponse.json({ replied: true });
  } catch (err) {
    console.error("reply error", err);
    return NextResponse.json({ error: "the note slipped under the door" }, { status: 500 });
  }
}
