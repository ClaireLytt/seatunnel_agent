import { NextResponse } from "next/server";
import { GoodNews } from "@/app/lib/perma";
import { readCollection, writeCollection } from "@/app/lib/store";

export const runtime = "nodejs";

// Light a lamp back for someone else's good news.
export async function POST(req: Request) {
  try {
    const body = (await req.json()) as { id?: string; clientId?: string };
    const id = String(body.id ?? "").slice(0, 64);
    const clientId = String(body.clientId ?? "").trim().slice(0, 64);
    if (!id || !clientId) {
      return NextResponse.json({ error: "missing id or clientId" }, { status: 400 });
    }

    const list = await readCollection<GoodNews>("goodnews");
    const note = list.find(n => n.id === id);
    // seed notes are not in the store; accept silently so the gesture still lands
    if (!note) return NextResponse.json({ lit: true, litCount: 1 });
    if (note.clientId === clientId) {
      return NextResponse.json({ error: "cannot light your own lamp" }, { status: 400 });
    }

    note.litBy = note.litBy ?? [];
    if (!note.litBy.includes(clientId)) {
      note.litBy.push(clientId);
      await writeCollection("goodnews", list);
    }
    return NextResponse.json({ lit: true, litCount: note.litBy.length });
  } catch (err) {
    console.error("lamp error", err);
    return NextResponse.json({ error: "the lamp flickers" }, { status: 500 });
  }
}
